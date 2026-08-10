# Changelog

All notable changes to QR-Code-Generator-Pro will be documented in this file.

## [v8.0.0] - 2026-08-03

- Added a headless QR core with validated payload builders, Python API, CLI, CSV batch generation, folder watch mode, and ZIP export.
- Added SVG path, PDF, EPS, WebP/GIF animation, favicon-pack, print-layout, preset, logo-overlay, pattern-background, frame, eye-style, and custom-mask exports.
- Added OpenCV round-trip decoding and expanded the desktop Save/Export menu with vector, print, animation, and favicon workflows.
- Added visual gradient editing, all structured payload builders, bulk style-grid manifests, preset import/export, clipboard/image/webcam decoding, print-sheet export, localization controls, and keyboard-focused accessibility affordances.

## [v7.0.0] - 2026-04-13

- Added: Add screenshot to README
- Added: Add screenshot to README
- Added: Add files via upload
- Changed: Update README.md

## Roadmap archive — 2026-08-10 — ROADMAP.md

<details>
<summary>Original roadmap snapshot</summary>

```markdown
# QR Code Generator Pro Roadmap

PyQt/Tk QR generator with 98 preset style families, gradients, and transparent PNG output. Roadmap adds batch, logo overlays, vector export, and a QR code reader path.

## Planned Features

### Output & Formats

### Styling

### Batch

### Input Types

### Reader / Decoder

### Automation

## Competitive Research
- **QRCode Monkey** — free web tool with logos + colors. Lesson: logo placement + preset eye patterns are table stakes; our wedge is offline + 344 styles.
- **Beaconstac / QR Code Generator (the paid one)** — dynamic QR with analytics. Lesson: out of scope (requires backend), but advertise "static, forever-free" clearly.
- **python-qrcode / segno** — libraries. Lesson: wrap segno for higher-quality SVG output.
- **zxing / pyzbar** — decoders. Lesson: reuse rather than reimplement for the reader feature.

## Nice-to-Haves

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
```

</details>
