# md2png-lite

[English](README.md) · [中文](README_zh.md)

Pure Python Markdown renderer that outputs PNG images.

## Goals

- No browser dependency
- No WeasyPrint dependency
- Cross-platform `pip install`
- Configurable themes
- Markdown + syntax highlight + basic math support

## Rendering approach

- It parses Markdown with `markdown-it-py` + `dollarmath`, maps tokens into a small document model, then lays out headings, paragraphs, tables, quotes, images, and code blocks directly on a Pillow canvas. No browser and no HTML screenshot step.
- Font selection is based on glyph coverage instead of one fixed font. It auto-discovers system/custom fonts, scores coverage with `matplotlib.ft2font`, preselects body/heading/code fonts, then falls back per text run for CJK and missing glyphs.
- Emoji are detected as Unicode sequences and rendered through cached Twemoji PNG assets, so skin-tone modifiers and common ZWJ sequences do not depend on local color-font availability.
- There are now two separate font routes: the default package stays on local system fonts, while the optional `NotoSans` extra syncs a curated Noto pack into a user cache directory and prefers that pack at render time.
- Math is rendered with `matplotlib.mathtext` into transparent bitmaps, with a light LaTeX sanitizing pass and a readable plain-text fallback for unsupported syntax.
- Syntax highlight comes from `Pygments` token streams, while wrapping and painting are handled by the renderer itself, so code blocks do not depend on browser CSS/JS.

## Install

```bash
pip install md2png-lite

# local development
uv sync
```

System-font route:

```bash
pip install md2png-lite
```

Curated Noto route:

```bash
pip install 'md2png-lite[NotoSans]'
```

The `NotoSans` extra does not embed fonts into the wheel. It installs the sync helpers and downloads the curated Noto pack into the local cache on first use.

## CLI

```bash
uv run md2png-lite input.md -o output.png --theme paper
```

Use the mobile summary preset with theme-driven width / padding / scale defaults:

```bash
uv run md2png-lite input.md -o output.png --theme mobile-summary
```

If you want serialized image content on stdout instead of a file:

```bash
uv run md2png-lite input.md --stdout-format base64
uv run md2png-lite input.md --stdout-format json
```

- `base64`: prints only the PNG base64 payload
- `json`: prints the full payload with `ok`, `renderer`, `mime_type`, and `base64`

Choose the font route explicitly at call time:

```bash
uv run md2png-lite input.md -o output.png --font-pack system
uv run md2png-lite input.md -o output.png --font-pack noto
```

Load custom fonts explicitly:

```bash
uv run md2png-lite input.md -o output.png \
  --font-path ./fonts/NotoSansCJKsc-Regular.otf \
  --font-dir ./fonts
```

## Stress Test

```bash
python3 scripts/benchmark_examples.py --repeat 3 --keep
```

This renders the bundled stress samples and prints timing / output size.

## Visual Check Samples

Render the smaller inspection-focused samples:

```bash
python3 scripts/render_examples.py
```

Use a custom glob when needed:

```bash
python3 scripts/render_examples.py --pattern 'sample_*.md'
```

## Python

```python
from md2png_lite import render_markdown_image

payload = render_markdown_image("# Hello\n\n```python\nprint('hi')\n```")
```

Choose the route per call:

```python
payload = render_markdown_image(markdown, font_pack="system")
payload = render_markdown_image(markdown, font_pack="noto")
payload = render_markdown_image(markdown, theme="mobile-summary")
```

Returned payload shape:

```python
{
    "ok": True,
    "renderer": "md2png-lite",
    "mime_type": "image/png",
    "base64": "...",
}
```

## Supported syntax

- Headings
- Paragraphs
- Bullet / ordered lists
- Block quotes
- Horizontal rules
- Fenced code blocks
- Custom `summary` fenced blocks rendered as editorial summary cards
- Inline code
- Tables
- Links / emphasis / strong / strikethrough
- Inline and block math via `matplotlib.mathtext`
- Local / `data:` / remote images

## Themes

- `paper`: current warm reading style; legacy alias `阅读器` remains available
- `github-light`: GitHub-like daytime theme
- `github-dark`: GitHub-like dark theme
- `solarized-light`: classic Solarized light theme
- `graphite`: existing dark editorial theme
- `mobile-summary`: phone-friendly editorial summary theme with large type and neutral `#f2f2f2` surfaces

## Font discovery

- Auto-discovers system fonts on macOS / Windows / Linux
- Supports two separate routes: `system` and synced `noto`
- Chooses fonts per text run instead of forcing one global font
- Prioritizes CJK-capable fonts for Chinese / Japanese / Korean text
- `font_pack="system"` stays on platform fonts only
- `font_pack="noto"` syncs the curated Noto pack into the local cache and prefers it
- Supports custom fonts through CLI: `--font-path`, `--font-dir`
- Supports route selection through CLI: `--font-pack auto|system|noto`
- Supports provider config: `md2png_lite.font_paths`, `md2png_lite.font_dirs`, `md2png_lite.font_pack`
- Supports environment variables: `MD2PNG_LITE_FONT_PATHS`, `MD2PNG_LITE_FONT_DIRS`, `MD2PNG_LITE_FONT_PACK`
- Supports emoji cache control through environment variables: `MD2PNG_LITE_EMOJI_CACHE_DIR`, `MD2PNG_LITE_EMOJI_SOURCE`

Synced Noto font license note:

- `licenses/NOTO_CJK_LICENSE.txt`

## Boundaries

- Math support follows `matplotlib.mathtext`, not full LaTeX
- HTML blocks are rendered as plain text
- Deeply nested lists / tables are supported, but layout remains image-oriented rather than browser-perfect
