from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _src_root() -> Path:
    return _repo_root() / "src"


def _load_helpers():
    sys.path.insert(0, str(_src_root()))
    try:
        from md2png_lite.font_sync import resolved_font_pack
        from md2png_lite.renderer import DEFAULT_PAGE_WIDTH, DEFAULT_SCALE, render_markdown_image
        from md2png_lite.theme import list_themes
    except Exception as exc:  # pragma: no cover - helper script path
        raise SystemExit(
            "Failed to import md2png_lite. "
            "Install project deps first, e.g. "
            "`uv pip install -e .` or `uv sync`.\n"
            f"Original error: {exc}"
        ) from exc
    return render_markdown_image, resolved_font_pack, list_themes, DEFAULT_PAGE_WIDTH, DEFAULT_SCALE


def _resolve_input(root: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.is_file():
        return path
    candidate = root / raw
    if candidate.is_file():
        return candidate
    raise SystemExit(f"Markdown file not found: {raw}")


def _default_inputs(root: Path) -> list[Path]:
    examples_dir = root / "examples"
    return sorted(path for path in examples_dir.glob("*.md") if path.is_file())


def main(argv: list[str] | None = None) -> int:
    render_markdown_image, resolved_font_pack, list_themes, default_width, default_scale = _load_helpers()
    parser = argparse.ArgumentParser(
        description="Render Markdown cases through both font routes and write system/noto PNG outputs."
    )
    parser.add_argument("inputs", nargs="*", help="Markdown files to render. Defaults to all examples/*.md")
    parser.add_argument("--theme", action="append", dest="themes", choices=list_themes(), default=[])
    parser.add_argument("--title", default="")
    parser.add_argument("--width", type=int, default=0)
    parser.add_argument("--scale", type=float, default=0.0)
    parser.add_argument("--out-dir", default="out/font-routes")
    args = parser.parse_args(argv)
    root = _repo_root()
    sources = [_resolve_input(root, raw) for raw in args.inputs] if args.inputs else _default_inputs(root)
    if not sources:
        raise SystemExit("No markdown cases found under examples/.")
    out_dir = (root / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    width = args.width or default_width
    scale = args.scale or default_scale

    themes = args.themes or list_themes()
    print(f"Cases={len(sources)}")
    print(f"Themes={', '.join(themes)} width={width} scale={scale}")

    for source in sources:
        text = source.read_text(encoding="utf-8")
        title = str(args.title or "")
        print(f"\nInput={source}")
        for requested_pack in ("system", "noto"):
            effective_pack = resolved_font_pack(requested_pack)
            for theme_name in themes:
                route_dir = out_dir / requested_pack / theme_name
                route_dir.mkdir(parents=True, exist_ok=True)
                payload = render_markdown_image(
                    text,
                    title=title,
                    theme=theme_name,
                    width=width,
                    scale=scale,
                    font_pack=requested_pack,
                )
                png_bytes = base64.b64decode(str(payload.get("base64") or ""))
                output = route_dir / f"{source.stem}.png"
                output.write_bytes(png_bytes)
                print(
                    f"{requested_pack}/{theme_name} -> {output} "
                    f"(effective={effective_pack}, {len(png_bytes) / 1024:.1f}KB)"
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
