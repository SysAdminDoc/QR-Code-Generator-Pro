# QR Code Generator Pro Roadmap

PyQt/Tk QR generator with 98 preset style families, gradients, and transparent PNG output. Roadmap adds batch, logo overlays, vector export, and a QR code reader path.

## Planned Features

### Output & Formats
- SVG export (vector, paths)
- PDF export with DPI and bleed controls
- EPS export for print workflows
- Favicon pack export (16 / 32 / 48 / 192)
- Animated QR (WebP / GIF) with cycling color / mask

### Styling
- Logo / image overlay with auto-safe-zone and error-correction bump
- Custom gradient editor (pick stops, angle, type)
- Pattern fill backgrounds (tile image)
- Frame templates ("Scan me" callout, arrow, branded border)
- Eye-pattern picker (corner finder) — swap square/round/leaf independently
- Custom module masks (stars, hearts, dots-with-spacing)

### Batch
- CSV batch: column → QR with per-row filename template
- Folder watch mode (drop TXT → get PNG)
- Bulk style grid (one payload rendered in every preset → pick)
- ZIP export of batch run

### Input Types
- vCard 4.0 builder (name, phone, email, org, photo)
- Wi-Fi credentials (SSID, auth, hidden flag) with preview password strength
- SMS / WhatsApp / tel: / mailto: builders
- Crypto address QR (BIP-21 bitcoin:, ethereum:)
- Geo: lat/long picker with Leaflet
- Event (vCalendar / ICS) builder
- OTP seed (otpauth://) generator for 2FA

### Reader / Decoder
- Paste-image decode (opencv + zbar or pyzbar)
- Webcam live decode
- "Round-trip test" — decode the just-generated QR to validate data

### Automation
- CLI: `qrgen "https://..." --style neon-03 --logo logo.png --out qr.svg`
- Python API so other scripts can import

## Competitive Research
- **QRCode Monkey** — free web tool with logos + colors. Lesson: logo placement + preset eye patterns are table stakes; our wedge is offline + 344 styles.
- **Beaconstac / QR Code Generator (the paid one)** — dynamic QR with analytics. Lesson: out of scope (requires backend), but advertise "static, forever-free" clearly.
- **python-qrcode / segno** — libraries. Lesson: wrap segno for higher-quality SVG output.
- **zxing / pyzbar** — decoders. Lesson: reuse rather than reimplement for the reader feature.

## Nice-to-Haves
- Preset import/export (`.qrpreset` JSON)
- Dark mode follows Windows accent color
- Drag-and-drop image to auto-fill Wi-Fi / vCard input
- Print layout wizard (sticker sheets, Avery templates)
- Localization
- Accessibility audit — keyboard-only flow, screen-reader labels

## Open-Source Research (Round 2)

### Related OSS Projects
- https://github.com/lincolnloop/python-qrcode — Canonical Python QR lib, StyledPilImage + module_drawer API.
- https://github.com/mpaolino/qrlib — Deep style controls (inner/outer eye, color, PDF/GIF output).
- https://github.com/komonaelliy/qr-code-generator — PyQt QR app with types (WiFi, vCard), logos, history.
- https://github.com/AdrianCeku/qrcode-generator-GUI — customtkinter + live preview + logo embedding.
- https://github.com/nayuki/QR-Code-generator — Multi-language reference implementation, bit-level correctness.
- https://github.com/zxing-js/library — ZXing JS port, the industry standard decoder; handy for round-trip tests.
- https://github.com/kazuhikoarase/qrcode-generator — JS QR gen, reference for fancy mask/ECC behavior.
- https://github.com/htv2012/qrstyle — Eye-style / body-style experimentation ground.

### Features to Borrow
- Inner-eye / outer-eye independently styled (mpaolino/qrlib) — currently presets may couple them.
- Error-correction forced to H when logo > 25% area (AdrianCeku).
- PDF and animated GIF output formats (mpaolino/qrlib).
- WiFi + vCard + MeCard + SMS + email payload builders as dedicated tabs (komonaelliy).
- Scannability validator — decode the generated QR with ZXing/zbar-py and warn if failure rate > threshold.
- Batch mode: CSV → N QR PNGs with filename template.
- SVG output for infinitely scalable print (lincolnloop w/ SvgFragmentImage).
- Micro-QR and rMQR (rectangular) support for tight labeling use cases.

### Patterns & Architectures Worth Studying
- **module_drawer + color_mask + embedded_image** (lincolnloop) — compositional styling, swap drawers without re-encoding.
- **Eye style as a separate ModuleDrawer subclass** (mpaolino/qrlib) — no special-casing the eye squares in the main drawer.
- **Decode-the-encode smoke test in CI** — every preset QR decodes via zbar-py on every commit.
- **Preset family as JSON manifest** — each of the 98 preset families is a JSON file, hot-reloadable at runtime.
- **GPU/PIL dual render path** — complex gradients + shaped modules run via moderngl for large print sizes.
