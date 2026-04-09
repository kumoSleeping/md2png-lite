from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

from .renderer import render_markdown_image
from .theme import list_themes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render Markdown into a PNG image with Pillow.")
    parser.add_argument("input", nargs="?", help="Markdown file path. Reads stdin when omitted.")
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("-o", "--output", help="PNG output path.")
    mode_group.add_argument(
        "--stdout-format",
        choices=("base64", "json"),
        help="Write serialized image content to stdout instead of a file.",
    )
    parser.add_argument("--title", default="Markdown Render")
    parser.add_argument("--theme", default="paper", help=f"Theme name or alias. Canonical themes: {', '.join(list_themes())}.")
    parser.add_argument("--accent", default="")
    parser.add_argument("--width", type=int, default=None, help="Page width in px. Omit to use the theme default.")
    parser.add_argument("--padding", type=int, default=None, help="Canvas padding in px. Omit to use the theme default.")
    parser.add_argument("--scale", type=float, default=None, help="Typography scale. Omit to use the theme default.")
    parser.add_argument("--font-path", action="append", default=[], help="Additional font file path. Repeatable.")
    parser.add_argument("--font-dir", action="append", default=[], help="Additional font directory. Repeatable.")
    parser.add_argument("--font-pack", choices=("auto", "system", "noto"), default="auto")
    args = parser.parse_args(argv)

    if args.input:
        markdown_text = Path(args.input).read_text(encoding="utf-8")
    else:
        markdown_text = sys.stdin.read()

    payload = render_markdown_image(
        markdown_text,
        title=args.title,
        theme=args.theme,
        accent=args.accent.strip() or None,
        width=args.width,
        padding=args.padding,
        scale=args.scale,
        font_paths=args.font_path,
        font_dirs=args.font_dir,
        font_pack=args.font_pack,
    )
    if args.stdout_format == "base64":
        sys.stdout.write(str(payload.get("base64") or ""))
        sys.stdout.write("\n")
        return 0
    if args.stdout_format == "json":
        json.dump(payload, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    target = Path(str(args.output)).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(base64.b64decode(str(payload.get("base64") or "")))
    return 0
