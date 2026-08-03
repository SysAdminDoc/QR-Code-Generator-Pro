"""Headless QR generation, payload builders, exports, and automation.

The Tk application remains the primary interactive surface, but all meaningful
QR work lives here so it can be used by scripts, tests, and packaged builds
without creating a window.
"""

# The core supports the project's Python 3.8 floor, so modern-union and
# typing-alias autofixes are intentionally not applied here.
# ruff: noqa: E501,UP006,UP007,UP017,UP035,UP038

from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import logging
import math
import re
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import quote, urlencode
from xml.sax.saxutils import escape as xml_escape

import qrcode
from PIL import Image, ImageDraw, ImageFont, ImageOps
from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import (
    HorizontalGradiantColorMask,
    RadialGradiantColorMask,
    SolidFillColorMask,
    SquareGradiantColorMask,
    VerticalGradiantColorMask,
)
from qrcode.image.styles.moduledrawers import (
    CircleModuleDrawer,
    GappedSquareModuleDrawer,
    HorizontalBarsDrawer,
    RoundedModuleDrawer,
    SquareModuleDrawer,
    VerticalBarsDrawer,
)

logger = logging.getLogger(__name__)


MODULE_DRAWER_CLASSES = {
    "square": SquareModuleDrawer,
    "rounded": RoundedModuleDrawer,
    "circle": CircleModuleDrawer,
    "gapped": GappedSquareModuleDrawer,
    "vertical_bars": VerticalBarsDrawer,
    "horizontal_bars": HorizontalBarsDrawer,
}

MODULE_DRAWER_NAMES = {
    "square": "Square",
    "rounded": "Rounded",
    "circle": "Circle",
    "gapped": "Gapped",
    "vertical_bars": "V-Bars",
    "horizontal_bars": "H-Bars",
}

ERROR_CORRECTION_LEVELS = {
    "L": ERROR_CORRECT_L,
    "M": ERROR_CORRECT_M,
    "Q": ERROR_CORRECT_Q,
    "H": ERROR_CORRECT_H,
    "LOW": ERROR_CORRECT_L,
    "MEDIUM": ERROR_CORRECT_M,
    "QUARTILE": ERROR_CORRECT_Q,
    "HIGH": ERROR_CORRECT_H,
    "LOW (7%)": ERROR_CORRECT_L,
    "MEDIUM (15%)": ERROR_CORRECT_M,
    "QUARTILE (25%)": ERROR_CORRECT_Q,
    "HIGH (30%)": ERROR_CORRECT_H,
}

PRESET_SCHEMA_VERSION = 1
EXPORT_FORMATS = {"png", "jpeg", "jpg", "bmp", "gif", "tiff", "webp", "pdf", "eps", "svg"}


def normalize_color(value: str) -> str:
    """Return a canonical six-digit HTML color or raise ``ValueError``."""

    if not isinstance(value, str):
        raise ValueError("color must be a string")
    value = value.strip()
    if not value.startswith("#"):
        value = "#" + value
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError("color must be a six-digit hexadecimal value")
    return value.upper()


def hex_to_rgb(value: str) -> Tuple[int, int, int]:
    value = normalize_color(value).lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _escape_vcard(value: Any) -> str:
    return str(value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _escape_wifi(value: Any) -> str:
    return str(value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace(":", "\\:").replace('"', '\\"')


def _mapping_value(payload: Mapping[str, Any], *names: str, default: Any = "") -> Any:
    for name in names:
        if name in payload and payload[name] is not None:
            return payload[name]
    return default


def _coerce_payload_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("structured payloads require a JSON object") from exc
        if isinstance(parsed, Mapping):
            return parsed
    raise ValueError("structured payloads require a JSON object")


def build_vcard_payload(contact: Mapping[str, Any]) -> str:
    """Build a vCard 4.0 payload from a mapping of contact fields."""

    first = _mapping_value(contact, "first_name", "first")
    last = _mapping_value(contact, "last_name", "last")
    display = _mapping_value(contact, "name", "fn", default=" ".join(str(x) for x in (first, last) if x).strip())
    lines = [
        "BEGIN:VCARD",
        "VERSION:4.0",
        f"FN:{_escape_vcard(display)}",
        f"N:{_escape_vcard(last)};{_escape_vcard(first)};;;",
    ]
    for field, label in (("phone", "TEL"), ("email", "EMAIL"), ("org", "ORG"), ("title", "TITLE"), ("url", "URL"), ("note", "NOTE")):
        value = _mapping_value(contact, field)
        if value:
            lines.append(f"{label}:{_escape_vcard(value)}")
    address = _mapping_value(contact, "address")
    if address:
        lines.append(f"ADR:;;{_escape_vcard(address)};;;;")
    lines.append("END:VCARD")
    return "\r\n".join(lines) + "\r\n"


def build_wifi_payload(ssid: str, password: str = "", auth: str = "WPA", hidden: bool = False) -> str:
    auth_value = str(auth or "nopass").upper()
    if auth_value in {"NONE", "OPEN"}:
        auth_value = "nopass"
    if auth_value not in {"WPA", "WEP", "NOPASS"}:
        raise ValueError("Wi-Fi authentication must be WPA, WEP, or nopass")
    return f"WIFI:T:{auth_value};S:{_escape_wifi(ssid)};P:{_escape_wifi(password)};H:{'true' if hidden else 'false'};;"


def _normalize_phone(value: Any) -> str:
    cleaned = re.sub(r"[\s\-().]", "", str(value or ""))
    if not re.fullmatch(r"\+?\d{7,15}", cleaned):
        raise ValueError("phone number must contain 7-15 digits")
    return cleaned if cleaned.startswith("+") else "+" + cleaned


def build_sms_payload(number: str, message: str = "") -> str:
    return f"SMSTO:{_normalize_phone(number)}:{message}" if message else f"SMSTO:{_normalize_phone(number)}"


def build_whatsapp_payload(number: str, message: str = "") -> str:
    digits = re.sub(r"\D", "", str(number or ""))
    if len(digits) < 7 or len(digits) > 15:
        raise ValueError("WhatsApp number must contain 7-15 digits")
    query = urlencode({"text": message}) if message else ""
    return f"https://wa.me/{digits}{'?' + query if query else ''}"


def build_mailto_payload(email: str, subject: str = "", body: str = "") -> str:
    email = str(email or "").strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValueError("email address is invalid")
    query = urlencode({key: value for key, value in (("subject", subject), ("body", body)) if value})
    return f"mailto:{email}{'?' + query if query else ''}"


def build_crypto_payload(currency: str, address: str, amount: Any = "", label: str = "", message: str = "") -> str:
    currency = str(currency or "bitcoin").lower().strip()
    if currency not in {"bitcoin", "btc", "ethereum", "eth", "litecoin", "ltc"}:
        raise ValueError("currency must be bitcoin, ethereum, or litecoin")
    scheme = {"btc": "bitcoin", "eth": "ethereum", "ltc": "litecoin"}.get(currency, currency)
    query = urlencode({key: value for key, value in (("amount", amount), ("label", label), ("message", message)) if value not in (None, "")})
    return f"{scheme}:{str(address).strip()}{'?' + query if query else ''}"


def build_geo_payload(latitude: Any, longitude: Any, label: str = "") -> str:
    lat = float(latitude)
    lon = float(longitude)
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("latitude must be -90..90 and longitude must be -180..180")
    query = f"?q={quote(str(label))}" if label else ""
    return f"geo:{lat:g},{lon:g}{query}"


def build_event_payload(event: Mapping[str, Any]) -> str:
    summary = _mapping_value(event, "summary", "title", default="QR Event")
    start = _mapping_value(event, "start", "dtstart")
    end = _mapping_value(event, "end", "dtend")
    if not start or not end:
        raise ValueError("event payload requires start and end")

    def format_date(value: Any) -> str:
        if isinstance(value, datetime):
            return value.strftime("%Y%m%dT%H%M%SZ")
        raw = str(value).strip()
        if re.fullmatch(r"\d{8}(T\d{6}Z)?", raw):
            return raw
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("event dates must be ISO-8601 or YYYYMMDDTHHMMSSZ") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//QRCodeGeneratorPro//EN", "BEGIN:VEVENT"]
    lines.extend([f"DTSTART:{format_date(start)}", f"DTEND:{format_date(end)}", f"SUMMARY:{_escape_vcard(summary)}"])
    for field, label in (("location", "LOCATION"), ("description", "DESCRIPTION"), ("url", "URL")):
        value = _mapping_value(event, field)
        if value:
            lines.append(f"{label}:{_escape_vcard(value)}")
    lines.extend(["END:VEVENT", "END:VCALENDAR"])
    return "\r\n".join(lines) + "\r\n"


def build_otp_payload(otp: Mapping[str, Any]) -> str:
    secret = str(_mapping_value(otp, "secret")).replace(" ", "").upper()
    if not re.fullmatch(r"[A-Z2-7]+=*", secret):
        raise ValueError("OTP secret must be base32")
    kind = str(_mapping_value(otp, "type", default="totp")).lower()
    if kind not in {"totp", "hotp"}:
        raise ValueError("OTP type must be totp or hotp")
    issuer = str(_mapping_value(otp, "issuer", default="QR Code Generator Pro"))
    account = str(_mapping_value(otp, "account", "name", default="account"))
    label = f"{issuer}:{account}" if issuer else account
    query: Dict[str, Any] = {"secret": secret}
    if issuer:
        query["issuer"] = issuer
    for key in ("algorithm", "digits", "period", "counter"):
        value = _mapping_value(otp, key)
        if value not in (None, ""):
            query[key] = value
    return f"otpauth://{kind}/{quote(label, safe=':')}?{urlencode(query)}"


def build_payload(input_type: str, value: Any, **kwargs: Any) -> str:
    """Build a standards-based payload for a UI or CLI input type."""

    kind = str(input_type or "text").lower().replace("-", "_").replace(" ", "_")
    if kind in {"url", "text"}:
        text = str(value or "").strip()
        if kind == "url" and not re.match(r"^https?://\S+", text, re.IGNORECASE):
            raise ValueError("URL must start with http:// or https://")
        if not text:
            raise ValueError("payload cannot be empty")
        return text
    if kind in {"phone", "tel", "telephone"}:
        return "tel:" + _normalize_phone(value)
    if kind in {"vcard", "contact"}:
        return build_vcard_payload(_coerce_payload_mapping(value))
    if kind in {"wifi", "wi_fi"}:
        payload = _coerce_payload_mapping(value) if isinstance(value, (Mapping, str)) and (isinstance(value, Mapping) or str(value).lstrip().startswith("{")) else {"ssid": value}
        return build_wifi_payload(str(_mapping_value(payload, "ssid", "name")), str(_mapping_value(payload, "password", "pass")), str(_mapping_value(payload, "auth", default="WPA")), bool(_mapping_value(payload, "hidden", default=False)))
    if kind in {"sms", "smsto"}:
        return build_sms_payload(str(_mapping_value(_coerce_payload_mapping(value), "number", "phone") if isinstance(value, Mapping) else value), str(kwargs.get("message", "")))
    if kind in {"whatsapp", "whats_app"}:
        return build_whatsapp_payload(str(_mapping_value(_coerce_payload_mapping(value), "number", "phone") if isinstance(value, Mapping) else value), str(kwargs.get("message", "")))
    if kind in {"mailto", "email", "mail"}:
        payload = _coerce_payload_mapping(value) if isinstance(value, Mapping) else {"email": value}
        return build_mailto_payload(str(_mapping_value(payload, "email", "address")), str(_mapping_value(payload, "subject", default=kwargs.get("subject", ""))), str(_mapping_value(payload, "body", default=kwargs.get("body", ""))))
    if kind in {"crypto", "bitcoin", "ethereum", "litecoin"}:
        payload = _coerce_payload_mapping(value) if isinstance(value, Mapping) else {"address": value, "currency": kind}
        return build_crypto_payload(str(_mapping_value(payload, "currency", default="bitcoin")), str(_mapping_value(payload, "address")), _mapping_value(payload, "amount"), str(_mapping_value(payload, "label")), str(_mapping_value(payload, "message")))
    if kind in {"geo", "location"}:
        payload = _coerce_payload_mapping(value)
        return build_geo_payload(_mapping_value(payload, "latitude", "lat"), _mapping_value(payload, "longitude", "lon", "lng"), str(_mapping_value(payload, "label", "query")))
    if kind in {"event", "ics", "calendar"}:
        return build_event_payload(_coerce_payload_mapping(value))
    if kind in {"otp", "otpauth"}:
        return build_otp_payload(_coerce_payload_mapping(value))
    raise ValueError(f"unsupported input type: {input_type}")


def validate_input_value(input_type: str, value: Any) -> Tuple[bool, str]:
    try:
        payload = build_payload(input_type, value)
    except (TypeError, ValueError) as exc:
        return False, str(exc)
    return True, f"{len(payload)} characters"


def resolve_error_correction(value: Any) -> int:
    key = str(value or "M").strip().upper()
    if key not in ERROR_CORRECTION_LEVELS:
        raise ValueError("error correction must be L, M, Q, or H")
    return ERROR_CORRECTION_LEVELS[key]


def ensure_logo_error_correction(value: Any, logo_scale: float) -> int:
    """Bump ECC to H when the logo would cover more than 25% of the code."""

    level = resolve_error_correction(value)
    if logo_scale > 0.25:
        return ERROR_CORRECT_H
    if level == ERROR_CORRECT_L and logo_scale > 0.16:
        return ERROR_CORRECT_M
    return level


def build_style_aliases(preset_families: Mapping[str, Mapping[str, Any]]) -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    category_indexes: Dict[str, int] = {}
    for family, config in preset_families.items():
        family_slug = _slug(family)
        drawers = list(config.get("drawers", ("square",)))
        for index, drawer in enumerate(drawers, 1):
            key = f"{family}|{drawer}"
            aliases[key.lower()] = key
            aliases[f"{family_slug}-{index:02d}"] = key
            aliases[f"{family_slug}-{drawer}"] = key
            aliases[f"{family_slug}-{MODULE_DRAWER_NAMES.get(drawer, drawer)}".lower()] = key
            for word in ("transparent", "classic", "corporate", "gradient", "neon", "retro", "elegant", "pastel", "soft", "dark", "vibrant"):
                if word in family_slug:
                    category_indexes[word] = category_indexes.get(word, 0) + 1
                    aliases[f"{word}-{category_indexes[word]:02d}"] = key
                    break
    return aliases


def resolve_style(style: Optional[str], preset_families: Mapping[str, Mapping[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    if not style:
        return None, None
    raw = str(style).strip()
    aliases = build_style_aliases(preset_families)
    direct = aliases.get(raw.lower())
    if direct:
        return tuple(direct.split("|", 1))  # type: ignore[return-value]
    slug = _slug(raw)
    direct = aliases.get(slug)
    if direct:
        return tuple(direct.split("|", 1))  # type: ignore[return-value]
    for family, config in preset_families.items():
        if _slug(family) == slug:
            return family, str(config.get("drawers", ["square"])[0])
    if "|" in raw:
        family, drawer = raw.split("|", 1)
        if family in preset_families and drawer in preset_families[family].get("drawers", ()):  # type: ignore[operator]
            return family, drawer
    choices = ", ".join(sorted(aliases)[:8])
    raise ValueError(f"unknown style '{style}'. Examples: {choices}")


def _resampling() -> Any:
    return getattr(Image, "Resampling", Image).LANCZOS


def _load_image(value: Any) -> Image.Image:
    if isinstance(value, Image.Image):
        return value.copy()
    with Image.open(Path(value)) as image:
        return image.copy()


def _rgba_color(color: Tuple[int, int, int], transparent: bool) -> Tuple[int, int, int, int]:
    return color + ((0,) if transparent else (255,))


def _gradient_color(first: Tuple[int, int, int], second: Tuple[int, int, int], x: float) -> Tuple[int, int, int, int]:
    amount = min(1.0, max(0.0, x))
    return tuple(round(first[index] + (second[index] - first[index]) * amount) for index in range(3)) + (255,)  # type: ignore[return-value]


def _gradient_position(kind: str, x: int, y: int, width: int, height: int) -> float:
    if kind == "vertical_gradient":
        return y / max(1, height - 1)
    if kind == "radial_gradient":
        return min(1.0, math.hypot(x - width / 2, y - height / 2) / max(1.0, math.hypot(width / 2, height / 2)))
    if kind == "square_gradient":
        return max(abs(x - width / 2) / max(1.0, width / 2), abs(y - height / 2) / max(1.0, height / 2))
    return x / max(1, width - 1)


def _draw_shape(draw: ImageDraw.ImageDraw, shape: str, bounds: Tuple[int, int, int, int], fill: Tuple[int, int, int, int]) -> None:
    left, top, right, bottom = bounds
    if shape == "circle" or shape == "dots":
        draw.ellipse(bounds, fill=fill)
    elif shape == "rounded":
        draw.rounded_rectangle(bounds, radius=max(1, (right - left) // 3), fill=fill)
    elif shape == "gapped":
        inset = max(1, (right - left) // 8)
        draw.rectangle((left + inset, top + inset, right - inset, bottom - inset), fill=fill)
    elif shape == "vertical_bars":
        inset = max(1, (right - left) // 5)
        draw.rectangle((left + inset, top, right - inset, bottom), fill=fill)
    elif shape == "horizontal_bars":
        inset = max(1, (bottom - top) // 5)
        draw.rectangle((left, top + inset, right, bottom - inset), fill=fill)
    elif shape == "star":
        cx = (left + right) / 2
        cy = (top + bottom) / 2
        radius = (right - left) / 2
        points = []
        for index in range(10):
            angle = -math.pi / 2 + index * math.pi / 5
            current = radius if index % 2 == 0 else radius * 0.42
            points.append((cx + math.cos(angle) * current, cy + math.sin(angle) * current))
        draw.polygon(points, fill=fill)
    elif shape == "heart":
        width = right - left
        height = bottom - top
        points = [(left + width * 0.5, bottom), (left, top + height * 0.35), (left + width * 0.2, top), (left + width * 0.5, top + height * 0.22), (left + width * 0.8, top), (right, top + height * 0.35)]
        draw.polygon(points, fill=fill)
    else:
        draw.rectangle(bounds, fill=fill)


def _draw_eye(draw: ImageDraw.ImageDraw, origin: Tuple[int, int], module: int, color: Tuple[int, int, int, int], background: Tuple[int, int, int, int], style: str) -> None:
    left, top = origin
    outer = (left, top, left + 7 * module - 1, top + 7 * module - 1)
    middle = (left + module, top + module, left + 6 * module - 1, top + 6 * module - 1)
    inner = (left + 2 * module, top + 2 * module, left + 5 * module - 1, top + 5 * module - 1)
    if style in {"circle", "round"}:
        draw.ellipse(outer, fill=color)
        draw.ellipse(middle, fill=background)
        draw.ellipse(inner, fill=color)
    elif style in {"leaf", "diamond"}:
        draw.polygon([(left + 3.5 * module, top), (left + 7 * module, top + 3.5 * module), (left + 3.5 * module, top + 7 * module), (left, top + 3.5 * module)], fill=color)
        draw.polygon([(left + 3.5 * module, top + module), (left + 6 * module, top + 3.5 * module), (left + 3.5 * module, top + 6 * module), (left + module, top + 3.5 * module)], fill=background)
        draw.polygon([(left + 3.5 * module, top + 2 * module), (left + 5 * module, top + 3.5 * module), (left + 3.5 * module, top + 5 * module), (left + 2 * module, top + 3.5 * module)], fill=color)
    else:
        draw.rectangle(outer, fill=color)
        draw.rectangle(middle, fill=background)
        draw.rectangle(inner, fill=color)


def _render_matrix(
    modules: Sequence[Sequence[bool]],
    box_size: int,
    border: int,
    fg_color: str,
    bg_color: str,
    transparent: bool,
    module_shape: str,
    gradient_type: Optional[str] = None,
    gradient_colors: Optional[Sequence[str]] = None,
    eye_style: str = "square",
    background_pattern: Optional[Any] = None,
) -> Image.Image:
    module_count = len(modules)
    total = (module_count + 2 * border) * box_size
    background = _rgba_color(hex_to_rgb(bg_color), transparent)
    if background_pattern and not transparent:
        tile = _load_image(background_pattern).convert("RGBA")
        tile.thumbnail((max(1, box_size * 8), max(1, box_size * 8)), _resampling())
        image = Image.new("RGBA", (total, total), background)
        for y in range(0, total, tile.height):
            for x in range(0, total, tile.width):
                image.alpha_composite(tile, (x, y))
    else:
        image = Image.new("RGBA", (total, total), background)
    draw = ImageDraw.Draw(image)
    first = hex_to_rgb(gradient_colors[0]) if gradient_colors else hex_to_rgb(fg_color)
    second = hex_to_rgb(gradient_colors[1]) if gradient_colors and len(gradient_colors) > 1 else first
    for row, values in enumerate(modules):
        for column, dark in enumerate(values):
            if not dark:
                continue
            x = (column + border) * box_size
            y = (row + border) * box_size
            fill = _gradient_color(first, second, _gradient_position(gradient_type or "horizontal_gradient", x, y, total, total)) if gradient_colors else _rgba_color(first, False)
            _draw_shape(draw, module_shape, (x, y, x + box_size - 1, y + box_size - 1), fill)
    if eye_style and eye_style.lower() not in {"square", "default"} and module_count >= 21:
        eye_color = _rgba_color(first, False)
        eye_background = background if not transparent else (255, 255, 255, 0)
        for origin in ((border * box_size, border * box_size), ((border + module_count - 7) * box_size, border * box_size), ((border * box_size, (border + module_count - 7) * box_size))):
            _draw_eye(draw, origin, box_size, eye_color, eye_background, eye_style.lower())
    return image


def _make_qr_matrix(data: str, error_correction: Any) -> List[List[bool]]:
    qr = qrcode.QRCode(version=None, error_correction=error_correction, box_size=1, border=0)
    qr.add_data(data)
    qr.make(fit=True)
    return [list(row) for row in qr.modules]


def _make_color_mask(gradient_type: Optional[str], gradient_colors: Optional[Sequence[str]], fg_color: str, bg_color: str, transparent: bool) -> Any:
    background: Tuple[int, ...] = hex_to_rgb(bg_color) + ((0,) if transparent else ())
    foreground = hex_to_rgb(fg_color) + ((255,) if transparent else ())
    if not gradient_colors:
        return SolidFillColorMask(back_color=background, front_color=foreground)
    first = hex_to_rgb(gradient_colors[0]) + ((255,) if transparent else ())
    second = hex_to_rgb(gradient_colors[1] if len(gradient_colors) > 1 else gradient_colors[0]) + ((255,) if transparent else ())
    kind = gradient_type or "horizontal_gradient"
    if kind == "vertical_gradient":
        return VerticalGradiantColorMask(back_color=background, top_color=first, bottom_color=second)
    if kind == "radial_gradient":
        return RadialGradiantColorMask(back_color=background, center_color=first, edge_color=second)
    if kind == "square_gradient":
        return SquareGradiantColorMask(back_color=background, center_color=first, edge_color=second)
    return HorizontalGradiantColorMask(back_color=background, left_color=first, right_color=second)


def add_logo_overlay(image: Image.Image, logo: Any, scale: float = 0.22, margin: float = 0.04, rounded: bool = True) -> Image.Image:
    """Place a logo in a padded white safe-zone in the QR center."""

    if not 0.05 <= scale <= 0.6:
        raise ValueError("logo scale must be between 0.05 and 0.6")
    logo_image = _load_image(logo).convert("RGBA")
    target = max(1, int(min(image.size) * scale))
    logo_image.thumbnail((target, target), _resampling())
    margin_px = max(2, int(min(image.size) * margin))
    panel_size = max(logo_image.width, logo_image.height) + margin_px * 2
    panel = Image.new("RGBA", (panel_size, panel_size), (255, 255, 255, 0))
    panel_draw = ImageDraw.Draw(panel)
    shape = (0, 0, panel_size - 1, panel_size - 1)
    if rounded:
        panel_draw.rounded_rectangle(shape, radius=max(2, margin_px), fill=(255, 255, 255, 255))
    else:
        panel_draw.rectangle(shape, fill=(255, 255, 255, 255))
    panel.alpha_composite(logo_image, ((panel_size - logo_image.width) // 2, (panel_size - logo_image.height) // 2))
    result = image.copy().convert("RGBA")
    result.alpha_composite(panel, ((result.width - panel.width) // 2, (result.height - panel.height) // 2))
    return result


def apply_frame_template(image: Image.Image, template: Optional[str], text: str = "Scan me", accent: str = "#7C3AED") -> Image.Image:
    """Add a print-friendly callout frame around a QR image."""

    if not template:
        return image
    template = template.lower().replace("_", "-")
    if template not in {"scan-me", "arrow", "branded-border", "border"}:
        raise ValueError("frame template must be scan-me, arrow, or branded-border")
    accent_rgb = hex_to_rgb(accent)
    padding = max(12, min(image.size) // 12)
    label_height = max(28, min(image.size) // 8) if template in {"scan-me", "arrow"} else 0
    canvas = Image.new("RGBA", (image.width + padding * 2, image.height + padding * 2 + label_height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((2, 2, canvas.width - 3, canvas.height - 3), radius=max(4, padding // 3), outline=accent_rgb + (255,), width=max(2, padding // 8))
    canvas.alpha_composite(image.convert("RGBA"), (padding, padding))
    if label_height:
        font = ImageFont.load_default()
        label = text or ("Scan me" if template == "scan-me" else "Open")
        box = draw.textbbox((0, 0), label, font=font)
        draw.text(((canvas.width - (box[2] - box[0])) // 2, image.height + padding + (label_height - (box[3] - box[1])) // 2), label, fill=accent_rgb + (255,), font=font)
        if template == "arrow":
            draw.polygon([(canvas.width // 2 - 8, image.height + padding + 5), (canvas.width // 2 + 8, image.height + padding + 5), (canvas.width // 2, image.height + padding - 3)], fill=accent_rgb + (255,))
    return canvas


def render_qr(
    data: str,
    *,
    style: Optional[str] = None,
    preset_families: Optional[Mapping[str, Mapping[str, Any]]] = None,
    fg_color: Optional[str] = None,
    bg_color: str = "#FFFFFF",
    transparent: bool = True,
    module_shape: Optional[str] = None,
    box_size: int = 10,
    border: int = 4,
    error_correction: Any = "M",
    gradient_type: Optional[str] = None,
    gradient_colors: Optional[Sequence[str]] = None,
    logo: Optional[Any] = None,
    logo_scale: float = 0.22,
    logo_margin: float = 0.04,
    eye_style: str = "square",
    module_mask: Optional[str] = None,
    background_pattern: Optional[Any] = None,
    frame_template: Optional[str] = None,
    frame_text: str = "Scan me",
    frame_accent: str = "#7C3AED",
) -> Image.Image:
    """Render a QR code as RGBA with the requested style and embellishments."""

    if not str(data).strip():
        raise ValueError("data cannot be empty")
    if box_size < 1 or box_size > 200:
        raise ValueError("box size must be between 1 and 200")
    if border < 0 or border > 20:
        raise ValueError("border must be between 0 and 20")
    families = preset_families or {}
    family_config: Mapping[str, Any] = {}
    if style and families:
        family, drawer = resolve_style(style, families)
        family_config = families.get(family or "", {})
        if module_shape is None:
            module_shape = drawer or "square"
        if fg_color is None:
            fg_color = str(family_config.get("fg_color", "#000000"))
        if gradient_colors is None:
            gradient_colors = family_config.get("gradient_colors")
        if gradient_type is None:
            gradient_type = family_config.get("color_mask")
    fg_color = normalize_color(fg_color or "#000000")
    bg_color = normalize_color(bg_color)
    module_shape = (module_shape or "square").lower().replace("-", "_")
    if module_shape in {"v_bars", "vbars"}:
        module_shape = "vertical_bars"
    if module_shape in {"h_bars", "hbars"}:
        module_shape = "horizontal_bars"
    if module_shape not in set(MODULE_DRAWER_CLASSES) | {"stars", "star", "hearts", "heart", "dots"}:
        raise ValueError(f"unsupported module shape: {module_shape}")
    if module_shape in {"stars", "star"}:
        module_shape = "star"
    elif module_shape in {"hearts", "heart"}:
        module_shape = "heart"
    elif module_shape == "dots":
        module_shape = "dots"
    if gradient_colors:
        gradient_colors = tuple(normalize_color(value) for value in gradient_colors)
        gradient_type = gradient_type or "horizontal_gradient"
    ecc = ensure_logo_error_correction(error_correction, logo_scale) if logo else resolve_error_correction(error_correction)
    use_manual = bool(logo or eye_style.lower() not in {"square", "default"} or module_shape in {"star", "heart", "dots"} or background_pattern)
    if use_manual:
        modules = _make_qr_matrix(str(data), ecc)
        image = _render_matrix(modules, int(box_size), int(border), fg_color, bg_color, transparent, module_shape, gradient_type, gradient_colors, eye_style, background_pattern)
    else:
        qr = qrcode.QRCode(version=None, error_correction=ecc, box_size=int(box_size), border=int(border))
        qr.add_data(str(data))
        qr.make(fit=True)
        drawer = MODULE_DRAWER_CLASSES.get(module_shape, SquareModuleDrawer)()
        color_mask = _make_color_mask(gradient_type, gradient_colors, fg_color, bg_color, transparent)
        image = qr.make_image(image_factory=StyledPilImage, module_drawer=drawer, color_mask=color_mask).convert("RGBA")
    if logo:
        image = add_logo_overlay(image, logo, logo_scale, logo_margin)
    if frame_template:
        image = apply_frame_template(image, frame_template, frame_text, frame_accent)
    return image


def _composite_rgb(image: Image.Image, background: Tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    if image.mode != "RGBA":
        return image.convert("RGB")
    canvas = Image.new("RGB", image.size, background)
    canvas.paste(image, mask=image.getchannel("A"))
    return canvas


def _with_bleed(image: Image.Image, bleed_mm: float, dpi: int, transparent: bool) -> Image.Image:
    if bleed_mm <= 0:
        return image
    pixels = max(1, round(bleed_mm / 25.4 * dpi))
    fill = (255, 255, 255, 0) if transparent and image.mode == "RGBA" else (255, 255, 255, 255)
    return ImageOps.expand(image, border=pixels, fill=fill)


def _image_data_uri(image: Image.Image, fmt: str = "PNG") -> str:
    stream = io.BytesIO()
    image.save(stream, format=fmt)
    return "data:image/{};base64,{}".format(fmt.lower(), base64.b64encode(stream.getvalue()).decode("ascii"))


def render_svg(
    data: str,
    *,
    style: Optional[str] = None,
    preset_families: Optional[Mapping[str, Mapping[str, Any]]] = None,
    fg_color: Optional[str] = None,
    bg_color: str = "#FFFFFF",
    transparent: bool = True,
    module_shape: Optional[str] = None,
    border: int = 4,
    error_correction: Any = "M",
    gradient_type: Optional[str] = None,
    gradient_colors: Optional[Sequence[str]] = None,
    logo: Optional[Any] = None,
    logo_scale: float = 0.22,
    logo_margin: float = 0.04,
    output_size: Optional[int] = None,
) -> str:
    """Render a scalable SVG composed of vector paths and optional embedded logo."""

    families = preset_families or {}
    family_config: Mapping[str, Any] = {}
    if style and families:
        family, drawer = resolve_style(style, families)
        family_config = families.get(family or "", {})
        module_shape = module_shape or drawer
        fg_color = fg_color or family_config.get("fg_color")
        gradient_colors = gradient_colors or family_config.get("gradient_colors")
        gradient_type = gradient_type or family_config.get("color_mask")
    fg_color = normalize_color(fg_color or "#000000")
    bg_color = normalize_color(bg_color)
    gradient_colors = tuple(normalize_color(value) for value in gradient_colors) if gradient_colors else None
    module_shape = (module_shape or "square").lower().replace("-", "_")
    aliases = {"v_bars": "vertical_bars", "h_bars": "horizontal_bars", "stars": "star", "hearts": "heart"}
    module_shape = aliases.get(module_shape, module_shape)
    ecc = ensure_logo_error_correction(error_correction, logo_scale) if logo else resolve_error_correction(error_correction)
    modules = _make_qr_matrix(str(data), ecc)
    count = len(modules)
    total = count + 2 * border
    size_attr = f' width="{output_size}" height="{output_size}"' if output_size else ""
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total} {total}"{size_attr} role="img" aria-label="QR code">']
    gradient_parts: List[str] = []
    if gradient_colors:
        kind = gradient_type or "horizontal_gradient"
        if kind == "vertical_gradient":
            attrs = 'x1="0%" y1="0%" x2="0%" y2="100%"'
        elif kind in {"radial_gradient", "square_gradient", "radial"}:
            gradient_parts.append(f'<radialGradient id="qr-gradient"><stop offset="0%" stop-color="{xml_escape(gradient_colors[0])}"/><stop offset="100%" stop-color="{xml_escape(gradient_colors[1] if len(gradient_colors) > 1 else gradient_colors[0])}"/></radialGradient>')
            fill = "url(#qr-gradient)"
            attrs = ""
        else:
            attrs = 'x1="0%" y1="0%" x2="100%" y2="0%"'
        if not gradient_parts:
            gradient_parts.append(f'<linearGradient id="qr-gradient" {attrs}><stop offset="0%" stop-color="{xml_escape(gradient_colors[0])}"/><stop offset="100%" stop-color="{xml_escape(gradient_colors[1] if len(gradient_colors) > 1 else gradient_colors[0])}"/></linearGradient>')
        fill = "url(#qr-gradient)"
    else:
        fill = xml_escape(fg_color)
    if gradient_parts:
        parts.append("<defs>" + "".join(gradient_parts) + "</defs>")
    if not transparent:
        parts.append(f'<rect width="{total}" height="{total}" fill="{xml_escape(bg_color)}"/>')
    path_commands: List[str] = []
    for row, values in enumerate(modules):
        for column, dark in enumerate(values):
            if not dark:
                continue
            x = column + border
            y = row + border
            if module_shape in {"circle", "dots"}:
                radius = 0.46 if module_shape == "circle" else 0.34
                cx, cy = x + 0.5, y + 0.5
                path_commands.append(f"M {cx - radius},{cy} a {radius},{radius} 0 1,0 {radius * 2},0 a {radius},{radius} 0 1,0 {-radius * 2},0")
            elif module_shape == "rounded":
                radius = 0.28
                path_commands.append(f"M{x + radius},{y}h{1 - 2 * radius}a{radius},{radius} 0 0 1 {radius},{radius}v{1 - 2 * radius}a{radius},{radius} 0 0 1 -{radius},{radius}h-{1 - 2 * radius}a{radius},{radius} 0 0 1 -{radius},-{radius}v-{1 - 2 * radius}a{radius},{radius} 0 0 1 {radius},-{radius}z")
            elif module_shape == "gapped":
                path_commands.append(f"M{x + .12},{y + .12}h.76v.76h-.76z")
            elif module_shape == "vertical_bars":
                path_commands.append(f"M{x + .2},{y}h.6v1h-.6z")
            elif module_shape == "horizontal_bars":
                path_commands.append(f"M{x},{y + .2}h1v.6h-1z")
            elif module_shape in {"star", "heart"}:
                # The compact paths stay vector-native while matching the raster mask.
                if module_shape == "star":
                    points = []
                    for index in range(10):
                        angle = -math.pi / 2 + index * math.pi / 5
                        radius = .5 if index % 2 == 0 else .21
                        points.append((x + .5 + math.cos(angle) * radius, y + .5 + math.sin(angle) * radius))
                    path_commands.append("M" + " L".join(f"{px:.3f},{py:.3f}" for px, py in points) + "z")
                else:
                    path_commands.append(f"M{x + .5},{y + .95}C{x},{y + .55} {x + .05},{y + .05} {x + .3},{y + .18}C{x + .5},{y + .3} {x + .5},{y + .3} {x + .7},{y + .18}C{x + .95},{y + .05} {x + 1},{y + .55} {x + .5},{y + .95}z")
            else:
                path_commands.append(f"M{x},{y}h1v1h-1z")
    parts.append(f'<path d="{" ".join(path_commands)}" fill="{fill}"/>')
    if logo:
        logo_image = _load_image(logo).convert("RGBA")
        logo_image.thumbnail((max(1, int(total * logo_scale)), max(1, int(total * logo_scale))), _resampling())
        data_uri = _image_data_uri(logo_image)
        margin = max(0.25, total * logo_margin)
        panel = max(logo_image.width, logo_image.height) + margin * 2
        x = (total - panel) / 2
        y = (total - panel) / 2
        parts.append(f'<rect x="{x:.3f}" y="{y:.3f}" width="{panel:.3f}" height="{panel:.3f}" rx="{min(panel / 5, margin):.3f}" fill="#FFFFFF"/>')
        parts.append(f'<image href="{data_uri}" x="{(total - logo_image.width) / 2:.3f}" y="{(total - logo_image.height) / 2:.3f}" width="{logo_image.width}" height="{logo_image.height}" preserveAspectRatio="xMidYMid meet"/>')
    parts.append("</svg>")
    return "".join(parts).replace('></svg>', '></svg>')


def export_pdf(image: Image.Image, output_path: Any, dpi: int = 300, bleed_mm: float = 0) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image = _with_bleed(image, bleed_mm, dpi, transparent=False)
    try:
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen.canvas import Canvas

        width_pt = image.width / dpi * 72
        height_pt = image.height / dpi * 72
        canvas = Canvas(str(path), pagesize=(width_pt, height_pt))
        canvas.setFillColorRGB(1, 1, 1)
        canvas.rect(0, 0, width_pt, height_pt, stroke=0, fill=1)
        canvas.drawImage(ImageReader(_composite_rgb(image)), 0, 0, width=width_pt, height=height_pt, preserveAspectRatio=True, mask="auto")
        canvas.showPage()
        canvas.save()
    except ImportError:
        _composite_rgb(image).save(path, "PDF", resolution=dpi)
    return path


def export_eps(image: Image.Image, output_path: Any, dpi: int = 300, bleed_mm: float = 0) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _composite_rgb(_with_bleed(image, bleed_mm, dpi, transparent=False)).save(path, "EPS", resolution=dpi)
    return path


def export_favicon_pack(image: Image.Image, output_dir: Any) -> List[Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for size in (16, 32, 48, 192):
        target = image.convert("RGBA").resize((size, size), _resampling())
        path = directory / f"favicon-{size}.png"
        target.save(path, "PNG", optimize=True)
        paths.append(path)
    ico_path = directory / "favicon.ico"
    image.convert("RGBA").save(ico_path, "ICO", sizes=[(16, 16), (32, 32), (48, 48), (192, 192)])
    paths.append(ico_path)
    return paths


def export_animated_qr(
    data: str,
    output_path: Any,
    *,
    frame_count: int = 8,
    duration_ms: int = 180,
    cycle: str = "color",
    styles: Optional[Sequence[str]] = None,
    render_options: Optional[Mapping[str, Any]] = None,
) -> Path:
    if frame_count < 2 or frame_count > 60:
        raise ValueError("frame count must be between 2 and 60")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    options = dict(render_options or {})
    frames: List[Image.Image] = []
    palette = ["#111827", "#7C3AED", "#DB2777", "#EA580C", "#16A34A", "#0891B2", "#2563EB", "#CA8A04"]
    for index in range(frame_count):
        frame_options = dict(options)
        if cycle.lower() in {"mask", "style"} and styles:
            frame_options["style"] = styles[index % len(styles)]
        else:
            frame_options["fg_color"] = palette[index % len(palette)]
        frame_options.pop("logo", None) if cycle.lower() == "mask" else None
        frames.append(render_qr(data, **frame_options).convert("RGBA"))
    fmt = output.suffix.lower()
    if fmt == ".webp":
        frames[0].save(output, "WEBP", save_all=True, append_images=frames[1:], duration=duration_ms, loop=0, lossless=True)
    else:
        gif_frames = [frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=256) for frame in frames]
        gif_frames[0].save(output, "GIF", save_all=True, append_images=gif_frames[1:], duration=duration_ms, loop=0, disposal=2)
    return output


def save_image(image: Image.Image, output_path: Any, fmt: Optional[str] = None, dpi: int = 300, bleed_mm: float = 0) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    format_name = (fmt or path.suffix.lstrip(".") or "png").lower()
    if format_name == "jpg":
        format_name = "jpeg"
    if format_name == "svg":
        raise ValueError("SVG requires render_svg because it is vector output")
    if format_name == "pdf":
        return export_pdf(image, path, dpi, bleed_mm)
    if format_name == "eps":
        return export_eps(image, path, dpi, bleed_mm)
    image = _with_bleed(image, bleed_mm, dpi, transparent=image.mode == "RGBA")
    if format_name in {"jpeg", "bmp"}:
        image = _composite_rgb(image)
    if format_name == "gif":
        image = image.convert("RGBA").convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
    save_kwargs: Dict[str, Any] = {}
    if format_name in {"png", "jpeg", "tiff"}:
        save_kwargs["dpi"] = (dpi, dpi)
    image.save(path, format_name.upper(), **save_kwargs)
    return path


def export_preset(output_path: Any, name: str, options: Mapping[str, Any]) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {"schema_version": PRESET_SCHEMA_VERSION, "name": str(name), "created_at": datetime.now(timezone.utc).isoformat(), "options": dict(options)}
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def import_preset(input_path: Any) -> Dict[str, Any]:
    document = json.loads(Path(input_path).read_text(encoding="utf-8"))
    if document.get("schema_version") != PRESET_SCHEMA_VERSION:
        raise ValueError("unsupported preset schema version")
    if not isinstance(document.get("options"), Mapping):
        raise ValueError("preset options must be an object")
    return dict(document)


def decode_qr_image(source: Any) -> List[str]:
    """Decode one or more QR symbols using OpenCV, then optional pyzbar."""

    image = _load_image(source)
    cv_error: Optional[Exception] = None
    cv_available = False
    try:
        import cv2
        import numpy as np

        cv_available = True
        array = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        detector = cv2.QRCodeDetector()
        found: List[str] = []
        try:
            ok, decoded, _, _ = detector.detectAndDecodeMulti(array)
            if ok:
                found.extend(value for value in decoded if value)
        except (AttributeError, cv2.error):
            pass
        if not found:
            value, _, _ = detector.detectAndDecode(array)
            if value:
                found.append(value)
        if found:
            return found
    except Exception as exc:  # optional backend, continue to pyzbar
        cv_error = exc
    try:
        from pyzbar.pyzbar import decode

        return [item.data.decode("utf-8", errors="replace") for item in decode(image.convert("RGB"))]
    except ImportError:
        if cv_available:
            return []
        if cv_error:
            raise RuntimeError(f"QR decoder unavailable: {cv_error}") from cv_error
        raise RuntimeError("install opencv-python or pyzbar to decode QR images") from None


def validate_round_trip(data: str, **render_options: Any) -> Dict[str, Any]:
    image = render_qr(data, **render_options)
    try:
        decoded = decode_qr_image(image)
    except RuntimeError as exc:
        return {"expected": data, "decoded": [], "valid": False, "matches": False, "error": str(exc)}
    return {"expected": data, "decoded": decoded, "valid": data in decoded, "matches": bool(decoded and decoded[0] == data)}


def decode_webcam(camera_index: int = 0, timeout_seconds: float = 15, on_detect: Optional[Callable[[str], None]] = None) -> List[str]:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("install opencv-python for webcam decoding") from exc
    camera = cv2.VideoCapture(camera_index)
    if not camera.isOpened():
        raise RuntimeError(f"cannot open webcam {camera_index}")
    detector = cv2.QRCodeDetector()
    results: List[str] = []
    deadline = time.monotonic() + timeout_seconds
    try:
        while time.monotonic() < deadline:
            ok, frame = camera.read()
            if not ok:
                continue
            value, _, _ = detector.detectAndDecode(frame)
            if value and value not in results:
                results.append(value)
                if on_detect:
                    on_detect(value)
                break
    finally:
        camera.release()
    return results


def _safe_filename(value: Any, fallback: str) -> str:
    text = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", str(value or "")).strip(" .")
    return text[:120] or fallback


def generate_batch_from_csv(
    csv_path: Any,
    output_dir: Any,
    *,
    data_column: str = "data",
    input_type: str = "text",
    filename_template: str = "{index}_{value}.png",
    style_column: Optional[str] = None,
    render_options: Optional[Mapping[str, Any]] = None,
) -> List[Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    results: List[Path] = []
    options = dict(render_options or {})
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        if not rows.fieldnames or data_column not in rows.fieldnames:
            raise ValueError(f"CSV column '{data_column}' was not found")
        for index, row in enumerate(rows, 1):
            raw = row.get(data_column, "")
            payload = build_payload(input_type, raw)
            row_options = dict(options)
            if style_column and row.get(style_column):
                row_options["style"] = row[style_column]
            image = render_qr(payload, **row_options)
            filename = filename_template.format(index=index, value=_safe_filename(raw, f"qr-{index}"), **{key: _safe_filename(value, "") for key, value in row.items()})
            target = output / _safe_filename(filename, f"qr-{index}.png")
            if not target.suffix:
                target = target.with_suffix(".png")
            save_image(image, target)
            results.append(target)
    return results


def zip_files(files: Iterable[Any], output_path: Any, base_dir: Optional[Any] = None) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    root = Path(base_dir).resolve() if base_dir else None
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for value in files:
            file_path = Path(value)
            if file_path.is_file():
                name = file_path.resolve().relative_to(root) if root else Path(file_path.name)
                archive.write(file_path, str(name).replace("\\", "/"))
    return path


def export_print_layout(
    image: Image.Image,
    output_path: Any,
    *,
    columns: int = 3,
    rows: int = 8,
    paper: str = "letter",
    margin_mm: float = 10,
    gap_mm: float = 3,
    label_text: str = "",
    dpi: int = 300,
) -> Path:
    if columns < 1 or rows < 1:
        raise ValueError("columns and rows must be positive")
    try:
        from reportlab.lib.pagesizes import A4, letter
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen.canvas import Canvas
    except ImportError as exc:
        raise RuntimeError("reportlab is required for print layout export") from exc
    page = A4 if paper.lower() == "a4" else letter
    margin = margin_mm / 25.4 * 72
    gap = gap_mm / 25.4 * 72
    cell_width = (page[0] - 2 * margin - (columns - 1) * gap) / columns
    cell_height = (page[1] - 2 * margin - (rows - 1) * gap) / rows
    label_height = 12 if label_text else 0
    side = max(1, min(cell_width, cell_height - label_height))
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas = Canvas(str(path), pagesize=page)
    rgb = _composite_rgb(image)
    for row in range(rows):
        for column in range(columns):
            x = margin + column * (cell_width + gap) + (cell_width - side) / 2
            y = page[1] - margin - (row + 1) * cell_height - row * gap + (cell_height - side - label_height) / 2
            canvas.drawImage(ImageReader(rgb), x, y, width=side, height=side, preserveAspectRatio=True, mask="auto")
            if label_text:
                canvas.setFont("Helvetica", 7)
                canvas.drawCentredString(x + side / 2, y - 9, label_text)
    canvas.showPage()
    canvas.save()
    return path


def watch_folder(
    input_dir: Any,
    output_dir: Any,
    *,
    poll_seconds: float = 1.0,
    stop_event: Optional[Any] = None,
    once: bool = False,
    render_options: Optional[Mapping[str, Any]] = None,
) -> List[Path]:
    source = Path(input_dir)
    target = Path(output_dir)
    source.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True, exist_ok=True)
    processed: Dict[Path, float] = {}
    generated: List[Path] = []
    while True:
        for file_path in sorted(source.glob("*.txt")):
            modified = file_path.stat().st_mtime
            if processed.get(file_path) == modified:
                continue
            data = file_path.read_text(encoding="utf-8").strip()
            if not data:
                processed[file_path] = modified
                continue
            image = render_qr(data, **dict(render_options or {}))
            output = target / f"{file_path.stem}.png"
            save_image(image, output)
            processed[file_path] = modified
            generated.append(output)
        if once:
            return generated
        if stop_event is not None and stop_event.is_set():
            return generated
        time.sleep(max(0.1, poll_seconds))


def _parse_gradient(value: Optional[str]) -> Tuple[Optional[str], Optional[Tuple[str, str]]]:
    if not value:
        return None, None
    pieces = [part.strip() for part in value.split(":", 1)]
    kind = pieces[0].lower().replace("-", "_")
    colors = tuple(part.strip() for part in pieces[1].split(",")) if len(pieces) > 1 else None
    if colors and len(colors) == 1:
        colors = (colors[0], colors[0])
    return kind, colors  # type: ignore[return-value]


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate styled QR codes without opening the GUI.")
    parser.add_argument("data", nargs="?", help="payload text or JSON for structured input types")
    parser.add_argument("--version", action="store_true", help="print application version")
    parser.add_argument("--input-type", default="text", help="url, phone, text, vcard, wifi, sms, whatsapp, mailto, crypto, geo, event, or otp")
    parser.add_argument("--payload-json", help="JSON object or path to a JSON object for structured payloads")
    parser.add_argument("--style", help="style alias such as neon-03 or family|drawer")
    parser.add_argument("--module-shape", choices=["square", "rounded", "circle", "gapped", "vertical_bars", "horizontal_bars", "star", "heart", "dots"])
    parser.add_argument("--eye-style", choices=["square", "rounded", "circle", "leaf"], default="square")
    parser.add_argument("--module-mask", choices=["stars", "hearts", "dots"])
    parser.add_argument("--logo", type=Path)
    parser.add_argument("--logo-scale", type=float, default=0.22)
    parser.add_argument("--out", type=Path, help="output file")
    parser.add_argument("--format", choices=sorted(EXPORT_FORMATS), help="output format; otherwise inferred from --out")
    parser.add_argument("--fg", default="#000000", help="foreground color")
    parser.add_argument("--bg", default="#FFFFFF", help="background color")
    parser.add_argument("--opaque", action="store_true", help="use an opaque background")
    parser.add_argument("--size", type=int, default=10, help="QR module pixel size")
    parser.add_argument("--border", type=int, default=4)
    parser.add_argument("--error-correction", default="M", choices=["L", "M", "Q", "H"])
    parser.add_argument("--gradient", help="gradient type and colors, e.g. horizontal:#7c3aed,#06b6d4")
    parser.add_argument("--background-pattern", type=Path)
    parser.add_argument("--frame", dest="frame_template", choices=["scan-me", "arrow", "branded-border"])
    parser.add_argument("--frame-text", default="Scan me")
    parser.add_argument("--pdf-dpi", type=int, default=300)
    parser.add_argument("--bleed-mm", type=float, default=0)
    parser.add_argument("--favicon-dir", type=Path)
    parser.add_argument("--animate", action="store_true")
    parser.add_argument("--frames", type=int, default=8)
    parser.add_argument("--duration", type=int, default=180)
    parser.add_argument("--cycle", choices=["color", "mask", "style"], default="color")
    parser.add_argument("--round-trip", action="store_true")
    parser.add_argument("--decode", type=Path, help="decode a QR image instead of generating one")
    parser.add_argument("--webcam", action="store_true")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--batch-csv", type=Path)
    parser.add_argument("--column", default="data")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--filename-template", default="{index}_{value}.png")
    parser.add_argument("--zip", dest="zip_path", type=Path)
    parser.add_argument("--watch", type=Path, help="watch a folder of .txt payload files")
    parser.add_argument("--watch-output", type=Path)
    parser.add_argument("--watch-once", action="store_true")
    parser.add_argument("--print-layout", type=Path)
    parser.add_argument("--columns", type=int, default=3)
    parser.add_argument("--rows", type=int, default=8)
    parser.add_argument("--paper", default="letter", choices=["letter", "a4"])
    parser.add_argument("--label", default="")
    return parser


def cli_main(argv: Optional[Sequence[str]] = None, preset_families: Optional[Mapping[str, Mapping[str, Any]]] = None) -> int:
    parser = build_cli_parser()
    args = parser.parse_args(argv)
    if args.version:
        print("QR Code Generator Pro core")
        return 0
    if args.decode:
        for value in decode_qr_image(args.decode):
            print(value)
        return 0
    if args.webcam:
        values = decode_webcam(args.camera, args.timeout)
        for value in values:
            print(value)
        return 0 if values else 1
    if args.batch_csv:
        if not args.output_dir:
            parser.error("--output-dir is required with --batch-csv")
        options = {"style": args.style, "fg_color": args.fg, "bg_color": args.bg, "transparent": not args.opaque, "box_size": args.size, "border": args.border, "error_correction": args.error_correction}
        options = {key: value for key, value in options.items() if value is not None}
        files = generate_batch_from_csv(args.batch_csv, args.output_dir, data_column=args.column, input_type=args.input_type, filename_template=args.filename_template, render_options={**options, "preset_families": preset_families or {}})
        if args.zip_path:
            zip_files(files, args.zip_path, args.output_dir)
        print(f"Generated {len(files)} QR codes in {args.output_dir}")
        return 0
    if args.watch:
        if not args.watch_output:
            parser.error("--watch-output is required with --watch")
        options = {"style": args.style, "fg_color": args.fg, "bg_color": args.bg, "transparent": not args.opaque, "box_size": args.size, "border": args.border, "error_correction": args.error_correction, "preset_families": preset_families or {}}
        files = watch_folder(args.watch, args.watch_output, once=args.watch_once, render_options=options)
        print(f"Generated {len(files)} QR codes")
        return 0
    if not args.data and not args.payload_json:
        parser.error("data is required")
    value: Any = args.payload_json or args.data
    if args.payload_json and Path(args.payload_json).is_file():
        value = Path(args.payload_json).read_text(encoding="utf-8")
    if args.input_type not in {"url", "text", "phone"}:
        value = _coerce_payload_mapping(value)
    data = build_payload(args.input_type, value)
    gradient_type, gradient_colors = _parse_gradient(args.gradient)
    options = {"style": args.style, "preset_families": preset_families or {}, "fg_color": args.fg, "bg_color": args.bg, "transparent": not args.opaque, "module_shape": args.module_mask or args.module_shape, "box_size": args.size, "border": args.border, "error_correction": args.error_correction, "gradient_type": gradient_type, "gradient_colors": gradient_colors, "logo": args.logo, "logo_scale": args.logo_scale, "eye_style": args.eye_style, "background_pattern": args.background_pattern, "frame_template": args.frame_template, "frame_text": args.frame_text}
    if args.animate:
        if not args.out:
            parser.error("--out is required with --animate")
        export_animated_qr(data, args.out, frame_count=args.frames, duration_ms=args.duration, cycle=args.cycle, render_options=options)
        print(args.out)
        return 0
    if args.favicon_dir:
        image = render_qr(data, **options)
        for path in export_favicon_pack(image, args.favicon_dir):
            print(path)
    if args.print_layout:
        image = render_qr(data, **options)
        export_print_layout(image, args.print_layout, columns=args.columns, rows=args.rows, paper=args.paper, label_text=args.label, dpi=args.pdf_dpi)
        print(args.print_layout)
    if not args.out:
        if args.favicon_dir or args.print_layout:
            return 0
        parser.error("--out is required")
    output_format = (args.format or args.out.suffix.lstrip(".") or "png").lower()
    if output_format == "svg":
        svg_options = dict(options)
        svg_options.pop("box_size", None)
        svg_options.pop("background_pattern", None)
        svg_options.pop("frame_template", None)
        svg_options.pop("frame_text", None)
        svg_options.pop("eye_style", None)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render_svg(data, **svg_options), encoding="utf-8")
    else:
        image = render_qr(data, **options)
        save_image(image, args.out, output_format, dpi=args.pdf_dpi, bleed_mm=args.bleed_mm)
        if args.round_trip:
            result = validate_round_trip(data, **options)
            print(json.dumps(result, sort_keys=True))
    print(args.out)
    return 0


__all__ = [
    "add_logo_overlay", "apply_frame_template", "build_cli_parser", "build_crypto_payload", "build_event_payload", "build_geo_payload", "build_mailto_payload", "build_otp_payload", "build_payload", "build_sms_payload", "build_style_aliases", "build_vcard_payload", "build_wifi_payload", "build_whatsapp_payload", "decode_qr_image", "decode_webcam", "ensure_logo_error_correction", "export_animated_qr", "export_eps", "export_favicon_pack", "export_pdf", "export_print_layout", "export_preset", "generate_batch_from_csv", "hex_to_rgb", "import_preset", "normalize_color", "render_qr", "render_svg", "resolve_error_correction", "resolve_style", "save_image", "validate_input_value", "validate_round_trip", "watch_folder", "zip_files",
]
