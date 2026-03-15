from __future__ import annotations

import argparse
import base64
import sys
import time
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
    parser = argparse.ArgumentParser(description="Benchmark stress Markdown examples.")
    parser.add_argument("--repeat", type=int, default=1, help="Render each example N times.")
    parser.add_argument("--theme", default="paper")
    parser.add_argument("--width", type=int, default=0)
    parser.add_argument("--scale", type=float, default=0.0)
    parser.add_argument("--out-dir", default="out")
    parser.add_argument("--keep", action="store_true", help="Write PNG outputs for inspection.")
    args = parser.parse_args(argv)

    render_markdown_image, default_width, default_scale = _load_renderer()
    width = args.width or default_width
    scale = args.scale or default_scale
    root = _repo_root()
    examples_dir = root / "examples"
    out_dir = root / args.out_dir
    if args.keep:
        out_dir.mkdir(parents=True, exist_ok=True)

    examples = sorted(examples_dir.glob("stress_*.md"))
    if not examples:
        raise SystemExit("No stress examples found.")

    print(f"Theme={args.theme} width={width} scale={scale} repeat={args.repeat}")
    print(f"Examples={len(examples)}")
    total_t0 = time.perf_counter()
    total_bytes = 0

    for example in examples:
        text = example.read_text(encoding="utf-8")
        elapsed_runs: list[float] = []
        payload = None
        for _ in range(max(1, args.repeat)):
            t0 = time.perf_counter()
            payload = render_markdown_image(
                text,
                title="",
                theme=args.theme,
                width=width,
                scale=scale,
            )
            elapsed_runs.append(time.perf_counter() - t0)
        assert payload is not None
        png_bytes = base64.b64decode(str(payload.get("base64") or ""))
        total_bytes += len(png_bytes)
        avg_ms = sum(elapsed_runs) / len(elapsed_runs) * 1000
        best_ms = min(elapsed_runs) * 1000
        worst_ms = max(elapsed_runs) * 1000
        print(
            f"{example.name}: avg={avg_ms:.1f}ms "
            f"best={best_ms:.1f}ms worst={worst_ms:.1f}ms "
            f"png={len(png_bytes) / 1024:.1f}KB"
        )
        if args.keep:
            (out_dir / f"{example.stem}.{args.theme}.png").write_bytes(png_bytes)

    total_ms = (time.perf_counter() - total_t0) * 1000
    print(f"Total: {total_ms:.1f}ms, output={total_bytes / 1024:.1f}KB")
    if args.keep:
        print(f"Wrote PNGs to: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
