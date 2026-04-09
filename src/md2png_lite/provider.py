from __future__ import annotations

import asyncio
from typing import Any

from .renderer import render_markdown_image


def _optional_int(*values: Any) -> int | None:
    for value in values:
        if value in (None, "", 0):
            continue
        return int(value)
    return None


def _optional_float(*values: Any) -> float | None:
    for value in values:
        if value in (None, "", 0, 0.0):
            continue
        return float(value)
    return None


async def render_md2png_lite_result(
    markdown_text: str,
    title: str = "Markdown Render",
    theme_color: str = "#ef4444",
    **kwargs: Any,
) -> dict[str, Any]:
    config = kwargs.get("config") if isinstance(kwargs.get("config"), dict) else {}
    render_cfg = config.get("md2png_lite") if isinstance(config, dict) else {}
    theme = str(
        kwargs.get("theme")
        or (render_cfg.get("theme") if isinstance(render_cfg, dict) else "")
        or "paper"
    ).strip() or "paper"
    width = _optional_int(
        kwargs.get("width"),
        render_cfg.get("width") if isinstance(render_cfg, dict) else None,
    )
    padding = _optional_int(
        kwargs.get("padding"),
        render_cfg.get("padding") if isinstance(render_cfg, dict) else None,
    )
    scale = _optional_float(
        kwargs.get("scale"),
        render_cfg.get("scale") if isinstance(render_cfg, dict) else None,
    )
    font_paths = kwargs.get("font_paths")
    if not isinstance(font_paths, list):
        font_paths = render_cfg.get("font_paths") if isinstance(render_cfg, dict) else []
    font_dirs = kwargs.get("font_dirs")
    if not isinstance(font_dirs, list):
        font_dirs = render_cfg.get("font_dirs") if isinstance(render_cfg, dict) else []
    font_pack = str(
        kwargs.get("font_pack")
        or (render_cfg.get("font_pack") if isinstance(render_cfg, dict) else "")
        or "auto"
    ).strip() or "auto"
    accent = str(theme_color or (render_cfg.get("accent") if isinstance(render_cfg, dict) else "") or "").strip() or None
    return await asyncio.to_thread(
        render_markdown_image,
        markdown_text,
        title=title,
        theme=theme,
        accent=accent,
        width=width,
        padding=padding,
        scale=scale,
        font_paths=[str(item) for item in font_paths] if isinstance(font_paths, list) else None,
        font_dirs=[str(item) for item in font_dirs] if isinstance(font_dirs, list) else None,
        font_pack=font_pack,
    )
