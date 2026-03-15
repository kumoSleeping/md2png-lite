from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _src_root() -> Path:
    return _repo_root() / "src"


def _load_renderer():
    sys.path.insert(0, str(_src_root()))
    try:
        from md2png_lite.renderer import DEFAULT_PAGE_WIDTH, DEFAULT_SCALE, render_markdown_image
    except Exception as exc:  # pragma: no cover - helper script path
        raise SystemExit(
            "Failed to import md2png_lite. "
            "Install project deps first, e.g. "
            "`uv pip install -e .`.\n"
            f"Original error: {exc}"
        ) from exc
    return render_markdown_image, DEFAULT_PAGE_WIDTH, DEFAULT_SCALE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render small Markdown examples for visual inspection.")
    parser.add_argument("--pattern", default="sample_*.md", help="Glob pattern under examples/.")
    parser.add_argument("--theme", default="paper")
    parser.add_argument("--width", type=int, default=0)
    parser.add_argument("--scale", type=float, default=0.0)
    parser.add_argument("--out-dir", default="out")
    args = parser.parse_args(argv)

    render_markdown_image, default_width, default_scale = _load_renderer()
    width = args.width or default_width
    scale = args.scale or default_scale

    root = _repo_root()
    examples_dir = root / "examples"
    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    examples = sorted(examples_dir.glob(args.pattern))
    if not examples:
        raise SystemExit(f"No examples matched pattern: {args.pattern}")

    print(f"Theme={args.theme} width={width} scale={scale} pattern={args.pattern}")
    for example in examples:
        text = example.read_text(encoding="utf-8")
        payload = render_markdown_image(
            text,
            title="",
            theme=args.theme,
            width=width,
            scale=scale,
        )
        png_bytes = base64.b64decode(str(payload.get("base64") or ""))
        output = out_dir / f"{example.stem}.{args.theme}.png"
        output.write_bytes(png_bytes)
        print(f"{example.name} -> {output.relative_to(root)} ({len(png_bytes) / 1024:.1f}KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
