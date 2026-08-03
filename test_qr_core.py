import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image

from qr_core import (
    build_crypto_payload,
    build_event_payload,
    build_gradient_config,
    build_geo_payload,
    build_mailto_payload,
    build_otp_payload,
    build_payload,
    build_sms_payload,
    build_style_aliases,
    build_vcard_payload,
    build_wifi_payload,
    build_whatsapp_payload,
    export_animated_qr,
    export_favicon_pack,
    export_preset,
    export_style_grid,
    generate_batch_from_csv,
    import_preset,
    parse_qr_payload,
    render_qr,
    render_svg,
    resolve_style,
    save_image,
    validate_round_trip,
    zip_files,
)


def test_payload_builders_cover_standard_input_types():
    assert build_payload("url", "https://example.com") == "https://example.com"
    assert build_payload("phone", "(555) 123-4567") == "tel:+5551234567"
    assert build_vcard_payload({"first_name": "Ada", "last_name": "Lovelace"}).startswith("BEGIN:VCARD")
    assert build_wifi_payload("Office;WiFi", "p:word", "WPA", True) == "WIFI:T:WPA;S:Office\\;WiFi;P:p\\:word;H:true;;"
    assert build_sms_payload("5551234567", "Hello").startswith("SMSTO:+5551234567:")
    assert build_whatsapp_payload("+15551234567", "Hello").startswith("https://wa.me/15551234567?")
    assert build_mailto_payload("ada@example.com", "Hi").startswith("mailto:ada@example.com?")
    assert build_crypto_payload("bitcoin", "bc1qexample").startswith("bitcoin:")
    assert build_geo_payload(40.7, -74.0) == "geo:40.7,-74"
    assert "BEGIN:VEVENT" in build_event_payload({"summary": "Demo", "start": "2026-08-03T10:00:00Z", "end": "2026-08-03T11:00:00Z"})
    assert build_otp_payload({"issuer": "Demo", "account": "ada", "secret": "JBSWY3DPEHPK3PXP"}).startswith("otpauth://totp/")


def test_invalid_payloads_fail_cleanly():
    with pytest.raises(ValueError):
        build_payload("url", "example.com")
    with pytest.raises(ValueError):
        build_geo_payload(91, 0)
    with pytest.raises(ValueError):
        build_otp_payload({"secret": "not-base32"})


def test_style_aliases_resolve_family_and_category_aliases():
    families = {
        "Neon Blue": {"drawers": ["square", "rounded", "circle"]},
        "Classic": {"drawers": ["square"]},
    }
    aliases = build_style_aliases(families)
    assert "neon-01" in aliases
    assert resolve_style("neon-03", families) == ("Neon Blue", "circle")
    assert resolve_style("Classic", families) == ("Classic", "square")


def test_gradient_and_decoded_payload_helpers():
    config = build_gradient_config(("#000000", "#ffffff"), "linear", 45)
    assert config["gradient_colors"] == ["#000000", "#FFFFFF"]
    assert config["angle"] == 45.0
    assert parse_qr_payload("SMSTO:+15551234567:Hello")["fields"]["message"] == "Hello"
    assert parse_qr_payload("WIFI:T:WPA;S:Office;P:secret;H:false;;")["fields"]["ssid"] == "Office"


def test_render_and_svg_are_headless_and_vector_valid(tmp_path: Path):
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (40, 40), (220, 20, 80, 255)).save(logo)
    image = render_qr(
        "https://example.com",
        module_shape="star",
        eye_style="circle",
        gradient_type="horizontal_gradient",
        gradient_colors=("#7C3AED", "#06B6D4"),
        logo=logo,
        transparent=True,
        box_size=6,
    )
    assert image.mode == "RGBA"
    assert image.getpixel((0, 0))[3] == 0
    svg = render_svg("https://example.com", gradient_type="horizontal_gradient", gradient_colors=("#7C3AED", "#06B6D4"), logo=logo)
    ET.fromstring(svg)
    assert "<path" in svg and "<image" in svg


def test_all_static_exports_and_round_trip(tmp_path: Path):
    image = render_qr("https://example.com", transparent=False, box_size=8)
    for extension in ("png", "jpeg", "bmp", "gif", "tiff", "webp", "pdf", "eps"):
        output = tmp_path / f"qr.{extension}"
        save_image(image, output, extension)
        assert output.exists() and output.stat().st_size > 0
    result = validate_round_trip("https://example.com", transparent=False, box_size=10)
    assert result["valid"] is True


def test_animation_favicon_presets_batch_and_zip(tmp_path: Path):
    image = render_qr("batch", box_size=4)
    favicon_paths = export_favicon_pack(image, tmp_path / "favicon")
    assert {path.name for path in favicon_paths} == {"favicon-16.png", "favicon-32.png", "favicon-48.png", "favicon-192.png", "favicon.ico"}
    animated = export_animated_qr("animated", tmp_path / "animated.gif", frame_count=2, duration_ms=30)
    assert animated.exists()

    preset_path = export_preset(tmp_path / "demo.qrpreset", "Demo", {"style": "neon-01", "box_size": 8})
    assert import_preset(preset_path)["options"]["style"] == "neon-01"

    csv_path = tmp_path / "payloads.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["data", "style"])
        writer.writeheader()
        writer.writerow({"data": "one", "style": "square"})
        writer.writerow({"data": "two", "style": "circle"})
    outputs = generate_batch_from_csv(csv_path, tmp_path / "batch", style_column="style", render_options={"box_size": 4})
    assert len(outputs) == 2
    archive = zip_files(outputs, tmp_path / "batch.zip", tmp_path / "batch")
    assert archive.exists()


def test_style_grid_emits_pickable_manifest(tmp_path: Path):
    families = {"Classic": {"fg_color": "#000000", "bg_color": "#FFFFFF", "color_mask": "solid", "gradient_colors": None, "drawers": ["square", "circle"]}}
    result = export_style_grid("grid", families, tmp_path / "grid", render_options={"box_size": 3})
    assert result["contact_sheet"].exists()
    manifest = json.loads(result["manifest"].read_text(encoding="utf-8"))
    assert len(manifest["entries"]) == 2

