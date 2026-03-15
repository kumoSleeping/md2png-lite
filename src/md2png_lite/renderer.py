from __future__ import annotations

import base64
import io
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import httpx
from PIL import Image, ImageChops, ImageDraw, ImageFont
from pygments import lex
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.styles import get_style_by_name

from .model import (
    BlockNode,
    CodeBlock,
    CodeSpan,
    Document,
    Heading,
    ImageBlock,
    ImageSpan,
    InlineNode,
    LineBreak,
    ListBlock,
    ListItem,
    MathBlock,
    MathSpan,
    Paragraph,
    Quote,
    Rule,
    TableBlock,
    TextSpan,
)
from .fonts import FontRegistry, _NO_LINE_START_PUNCTUATION, _resolved_role
from .parser import parse_markdown_document
from .theme import RenderTheme, get_theme

RenderResult = dict[str, Any]
_DATA_IMAGE_RE = re.compile(r"^data:([^;,]+)?;base64,(.+)$", flags=re.IGNORECASE | re.DOTALL)
_LATEX_SANITIZE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\\lVert"), r"||"),
    (re.compile(r"\\rVert"), r"||"),
    (re.compile(r"\\le(?![a-zA-Z])"), r"\\leq"),
    (re.compile(r"\\ge(?![a-zA-Z])"), r"\\geq"),
    (re.compile(r"\\mathbb\{([^}]+)\}"), r"\\mathrm{\1}"),
    (re.compile(r"\\operatorname\{([^}]+)\}"), r"\\mathrm{\1}"),
    (re.compile(r"\\text\{([^}]+)\}"), r"\\mathrm{\1}"),
    (re.compile(r"\\arg\\max"), r"\\operatorname{argmax}"),
    (re.compile(r"\\arg\\min"), r"\\operatorname{argmin}"),
)

DEFAULT_PAGE_WIDTH = 1600
DEFAULT_PADDING = 56
DEFAULT_SCALE = 1.15


@dataclass(frozen=True)
class _FontPalette:
    body: int = 28
    code: int = 24
    quote: int = 26
    title: int = 18

    def heading(self, level: int) -> int:
        return {
            1: 50,
            2: 42,
            3: 36,
            4: 32,
            5: 28,
            6: 26,
        }.get(level, 26)


@dataclass
class _Run:
    kind: str
    width: int
    height: int
    text: str = ""
    font: ImageFont.ImageFont | None = None
    fill: str = "#000000"
    background: str = ""
    underline: bool = False
    strike: bool = False
    image: Image.Image | None = None
    pad_x: int = 0
    pad_y: int = 0
    is_space: bool = False
    ascent: int = 0
    descent: int = 0


@dataclass
class _Line:
    runs: list[_Run]
    width: int
    height: int
    ascent: int
    descent: int


@dataclass(frozen=True)
class _MathRender:
    image: Image.Image
    ascent: int
    descent: int


@dataclass(frozen=True)
class _RenderedCodeBlock:
    lines: list[_Line]
    line_numbers: list[str]
    language_label: str
    height: int
    pad_top: int
    pad_bottom: int
    pad_x: int
    gutter_width: int
    gutter_gap: int
    header_height: int


class PillowMarkdownRenderer:
    def __init__(
        self,
        *,
        width: int = DEFAULT_PAGE_WIDTH,
        padding: int = DEFAULT_PADDING,
        theme: str = "paper",
        accent: str | None = None,
        scale: float = DEFAULT_SCALE,
        font_paths: list[str] | None = None,
        font_dirs: list[str] | None = None,
        font_pack: str | None = None,
    ) -> None:
        self.page_width = max(720, int(width))
        self.padding = max(24, int(padding))
        self.theme = get_theme(theme, accent=accent)
        self.scale = max(1.0, float(scale or 1.0))
        self.fonts = _FontPalette(
            body=max(16, int(28 * self.scale)),
            code=max(15, int(26 * self.scale)),
            quote=max(16, int(26 * self.scale)),
            title=max(12, int(18 * self.scale)),
        )
        self._scratch_image = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        self._scratch_draw = ImageDraw.Draw(self._scratch_image)
        self._image_cache: dict[str, Image.Image | None] = {}
        self._math_cache: dict[tuple[str, int, str, bool], _MathRender | None] = {}
        self._font_registry = FontRegistry(font_paths=font_paths, font_dirs=font_dirs, font_pack=font_pack)
        self._primary_fonts: dict[tuple[str, str, bool, bool], Any] = {}

    def render_document(self, document: Document, *, title: str = "") -> RenderResult:
        self._prepare_primary_fonts(document, title=title)
        content_width = self.page_width - self.padding * 2
        top = self.padding
        title_text = str(title or "").strip()
        first_heading_text = self._first_heading_text(document)
        if title_text and first_heading_text and title_text.strip() == first_heading_text.strip():
            title_text = ""
        title_height = 0
        if title_text:
            title_height = self._font_height(self._heading_font_for_text(title_text, self.fonts.title, bold=False)) + int(18 * self.scale)

        measured_bottom = self._render_blocks(
            document.children,
            image=None,
            x=self.padding,
            y=top + title_height,
            width=content_width,
        )
        total_height = max(int(measured_bottom + self.padding), self.padding * 2 + 100)

        canvas = Image.new("RGBA", (self.page_width, total_height), self.theme.background)
        draw = ImageDraw.Draw(canvas)

        if title_text:
            title_font = self._heading_font_for_text(title_text, self.fonts.title)
            draw.text(
                (self.padding, top),
                title_text,
                font=title_font,
                fill=self.theme.muted,
            )

        self._render_blocks(
            document.children,
            image=canvas,
            x=self.padding,
            y=top + title_height,
            width=content_width,
        )

        buffer = io.BytesIO()
        canvas.save(buffer, format="PNG")
        return {
            "ok": True,
            "renderer": "md2png-lite",
            "mime_type": "image/png",
            "base64": base64.b64encode(buffer.getvalue()).decode(),
        }

    def render_markdown(self, markdown_text: str, *, title: str = "") -> RenderResult:
        document = parse_markdown_document(markdown_text)
        return self.render_document(document, title=title)

    def _render_blocks(
        self,
        blocks: Sequence[BlockNode],
        *,
        image: Image.Image | None,
        x: int,
        y: int,
        width: int,
    ) -> int:
        cursor_y = y
        for block in blocks:
            cursor_y = self._render_block(block, image=image, x=x, y=cursor_y, width=width)
        return cursor_y

    def _render_block(
        self,
        block: BlockNode,
        *,
        image: Image.Image | None,
        x: int,
        y: int,
        width: int,
    ) -> int:
        if isinstance(block, Heading):
            return self._render_rich_text_block(
                block.children,
                image=image,
                x=x,
                y=y,
                width=width,
                font_size=self.fonts.heading(block.level),
                color=self.theme.accent if block.level <= 2 else self.theme.foreground,
                spacing_after=int(24 * self.scale),
                role="heading",
            )
        if isinstance(block, Paragraph):
            return self._render_rich_text_block(
                block.children,
                image=image,
                x=x,
                y=y,
                width=width,
                font_size=self.fonts.body,
                color=self.theme.foreground,
                spacing_after=int(18 * self.scale),
                role="body",
            )
        if isinstance(block, Quote):
            return self._render_quote(block, image=image, x=x, y=y, width=width)
        if isinstance(block, ListBlock):
            return self._render_list(block, image=image, x=x, y=y, width=width)
        if isinstance(block, CodeBlock):
            return self._render_code_block(block, image=image, x=x, y=y, width=width)
        if isinstance(block, Rule):
            return self._render_rule(image=image, x=x, y=y, width=width)
        if isinstance(block, TableBlock):
            return self._render_table(block, image=image, x=x, y=y, width=width)
        if isinstance(block, MathBlock):
            return self._render_math_block(block, image=image, x=x, y=y, width=width)
        if isinstance(block, ImageBlock):
            return self._render_image_block(block, image=image, x=x, y=y, width=width)
        return y

    @staticmethod
    def _first_heading_text(document: Document) -> str:
        for block in document.children:
            if isinstance(block, Heading):
                return "".join(
                    node.text for node in block.children if isinstance(node, TextSpan)
                ).strip()
        return ""

    def _prepare_primary_fonts(self, document: Document, *, title: str = "") -> None:
        samples = self._document_text_samples(document)
        if title:
            samples["heading"] = f"{samples.get('heading', '')} {title}".strip()
        body_text = samples.get("body", "")
        heading_text = samples.get("heading", body_text)
        self._primary_fonts = {}

        for scope, sample_text in (("body", body_text), ("heading", heading_text)):
            role_samples = self._role_samples(sample_text)
            for role, sample in role_samples.items():
                self._primary_fonts[(scope, role, False, False)] = self._font_registry.primary_entry(
                    sample,
                    role=role,
                    bold=False,
                    italic=False,
                )
                self._primary_fonts[(scope, role, True, False)] = self._font_registry.primary_entry(
                    sample,
                    role=role,
                    bold=True,
                    italic=False,
                )
                self._primary_fonts[(scope, role, False, True)] = self._font_registry.primary_entry(
                    sample,
                    role=role,
                    bold=False,
                    italic=True,
                )

        code_sample = samples.get("code", "")
        self._primary_fonts[("code", "mono", False, False)] = self._font_registry.primary_entry(
            code_sample,
            role="mono",
            bold=False,
            italic=False,
        )
        self._primary_fonts[("code", "mono", True, False)] = self._font_registry.primary_entry(
            code_sample,
            role="mono",
            bold=True,
            italic=False,
        )

    def _document_text_samples(self, document: Document) -> dict[str, str]:
        bucket = {"body": "", "heading": "", "code": ""}

        def walk_block(block: BlockNode) -> None:
            if isinstance(block, Heading):
                bucket["heading"] += " " + self._inline_text_content(block.children)
                return
            if isinstance(block, Paragraph):
                bucket["body"] += " " + self._inline_text_content(block.children)
                return
            if isinstance(block, Quote):
                for child in block.children:
                    walk_block(child)
                return
            if isinstance(block, ListBlock):
                for item in block.items:
                    for child in item.children:
                        walk_block(child)
                return
            if isinstance(block, CodeBlock):
                bucket["code"] += " " + str(block.code or "")
                return
            if isinstance(block, MathBlock):
                bucket["body"] += " " + str(block.latex or "")
                return
            if isinstance(block, TableBlock):
                for row in [block.headers, *block.rows]:
                    for cell in row:
                        bucket["body"] += " " + self._inline_text_content(cell)
                return
            if isinstance(block, ImageBlock):
                bucket["body"] += " " + (block.alt or "")

        for block in document.children:
            walk_block(block)
        return {k: v.strip() for k, v in bucket.items()}

    @staticmethod
    def _script_bucket_for_text(text: str, *, default_role: str = "sans") -> str:
        return _resolved_role(str(text or ""), default_role)

    @classmethod
    def _role_samples(cls, text: str, *, default_role: str = "sans") -> dict[str, str]:
        buckets: dict[str, list[str]] = {}
        for chunk in re.split(r"(\s+)", str(text or "")):
            if not chunk or chunk.isspace():
                continue
            role = cls._script_bucket_for_text(chunk, default_role=default_role)
            buckets.setdefault(role, []).append(chunk)
        return {role: " ".join(parts).strip() for role, parts in buckets.items() if parts}

    def _render_quote(self, block: Quote, *, image: Image.Image | None, x: int, y: int, width: int) -> int:
        pad = int(18 * self.scale)
        border = max(4, int(5 * self.scale))
        inner_x = x + border + pad
        inner_width = max(120, width - border - pad * 2)
        content_top = y + pad
        content_bottom = self._render_blocks(block.children, image=None, x=inner_x, y=content_top, width=inner_width)
        if block.children:
            content_bottom = max(content_top, content_bottom - self._block_trailing_margin(block.children[-1]))
        content_height = max(0, int(content_bottom - content_top))
        total_height = max(content_height + pad * 2, int(52 * self.scale))
        if image is not None:
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle(
                (x, y, x + width, y + total_height),
                radius=max(8, int(10 * self.scale)),
                fill=self.theme.quote_background,
            )
            draw.rounded_rectangle(
                (x, y, x + border, y + total_height),
                radius=max(4, int(6 * self.scale)),
                fill=self.theme.quote_border,
            )
            self._render_blocks(block.children, image=image, x=inner_x, y=content_top, width=inner_width)
        return y + total_height + int(18 * self.scale)

    def _render_list(self, block: ListBlock, *, image: Image.Image | None, x: int, y: int, width: int) -> int:
        list_inset = int(18 * self.scale)
        marker_gap = int(14 * self.scale)
        marker_width = int(42 * self.scale)
        marker_x = x + list_inset
        body_x = marker_x + marker_width + marker_gap
        body_width = max(120, width - list_inset - marker_width - marker_gap)
        cursor_y = y
        marker_font = self._font(self.fonts.body, role="sans", bold=True)
        for idx, item in enumerate(block.items):
            item_top = cursor_y
            cursor_y = self._render_blocks(item.children, image=image, x=body_x, y=cursor_y, width=body_width)
            if image is not None:
                draw = ImageDraw.Draw(image)
                if block.ordered:
                    marker = f"{block.start + idx}."
                    marker_width_px = self._text_width(marker_font, marker)
                    draw.text(
                        (marker_x + max(0, marker_width - marker_width_px), item_top + int(2 * self.scale)),
                        marker,
                        font=marker_font,
                        fill=self.theme.accent,
                    )
                else:
                    radius = max(4, int(5 * self.scale))
                    cy = item_top + max(radius + 2, int(self._font_metrics(marker_font)[0] * 0.56))
                    cx = marker_x + marker_width // 2
                    draw.ellipse(
                        (cx - radius, cy - radius, cx + radius, cy + radius),
                        fill=self.theme.accent,
                    )
            cursor_y += int(2 * self.scale)
        return cursor_y + int(8 * self.scale)

    def _render_rule(self, *, image: Image.Image | None, x: int, y: int, width: int) -> int:
        mid_y = y + int(10 * self.scale)
        if image is not None:
            draw = ImageDraw.Draw(image)
            draw.line((x, mid_y, x + width, mid_y), fill=self.theme.border, width=max(1, int(2 * self.scale)))
        return y + int(22 * self.scale)

    def _render_math_block(self, block: MathBlock, *, image: Image.Image | None, x: int, y: int, width: int) -> int:
        rendered = self._render_math_image(block.latex, self.fonts.body + 20, self.theme.foreground, inline=False)
        if rendered is None:
            return self._render_rich_text_block(
                [TextSpan(text=f"${block.latex}$")],
                image=image,
                x=x,
                y=y,
                width=width,
                font_size=self.fonts.body,
                color=self.theme.foreground,
                spacing_after=int(18 * self.scale),
                role="body",
            )
        if rendered.image.width > width:
            rendered = self._scale_math_render(rendered, width / float(rendered.image.width))
        box_y = y + int(8 * self.scale)
        if image is not None:
            paste_x = x + max(0, (width - rendered.image.width) // 2)
            image.paste(rendered.image, (paste_x, box_y), rendered.image)
        return box_y + rendered.image.height + int(20 * self.scale)

    def _render_image_block(self, block: ImageBlock, *, image: Image.Image | None, x: int, y: int, width: int) -> int:
        loaded = self._load_image(block.source)
        if loaded is None:
            fallback = [TextSpan(text=block.alt or block.source or "[image]")]
            return self._render_rich_text_block(
                fallback,
                image=image,
                x=x,
                y=y,
                width=width,
                font_size=self.fonts.body,
                color=self.theme.muted,
                spacing_after=int(18 * self.scale),
                role="body",
            )
        target = self._scale_image(loaded, width=width, max_height=int(560 * self.scale))
        if image is not None:
            paste_x = x + max(0, (width - target.width) // 2)
            image.paste(target, (paste_x, y), target)
        cursor_y = y + target.height
        if block.alt:
            cursor_y = self._render_rich_text_block(
                [TextSpan(text=block.alt)],
                image=image,
                x=x,
                y=cursor_y + int(8 * self.scale),
                width=width,
                font_size=self.fonts.title,
                color=self.theme.muted,
                spacing_after=int(14 * self.scale),
                role="heading",
            )
        else:
            cursor_y += int(18 * self.scale)
        return cursor_y

    def _render_table(self, block: TableBlock, *, image: Image.Image | None, x: int, y: int, width: int) -> int:
        column_count = max(
            len(block.headers),
            max((len(row) for row in block.rows), default=0),
        )
        if column_count <= 0:
            return y

        gap = 0
        cell_pad_x = int(12 * self.scale)
        cell_pad_y = int(10 * self.scale)
        column_widths = self._table_column_widths(block, total_width=width - gap * (column_count + 1), min_width=max(80, int(88 * self.scale)))

        rows: list[tuple[bool, list[list[InlineNode]]]] = []
        if block.headers:
            rows.append((True, [cell for cell in block.headers]))
        rows.extend((False, row) for row in block.rows)

        measured_rows: list[tuple[bool, int, list[list[_Line]]]] = []
        for row in rows:
            is_header, cells = row
            measured: list[int] = []
            rendered_cells: list[list[_Line]] = []
            for cell_index in range(column_count):
                cell = cells[cell_index] if cell_index < len(cells) else []
                cell_width = column_widths[cell_index]
                lines = self._layout_inline_nodes(
                    cell,
                    width=cell_width - cell_pad_x * 2,
                    font_size=self.fonts.body,
                    color=self.theme.foreground,
                )
                rendered_cells.append(lines)
                height = self._lines_height(lines) + cell_pad_y * 2
                measured.append(max(height, int(34 * self.scale)))
            measured_rows.append((is_header, max(measured), rendered_cells))

        total_height = sum(row_height for _, row_height, _ in measured_rows) + gap * max(0, len(measured_rows) - 1)
        if image is not None and measured_rows:
            draw = ImageDraw.Draw(image)
            radius = max(4, int(6 * self.scale))
            draw.rounded_rectangle(
                (x, y, x + width, y + total_height),
                radius=radius,
                fill=self.theme.table_row_background,
                outline=self.theme.border,
                width=1,
            )

            cursor_y = y
            last_row_index = len(measured_rows) - 1
            for row_index, (is_header, row_height, rendered_cells) in enumerate(measured_rows):
                row_top = cursor_y
                row_bottom = row_top + row_height
                fill = self.theme.table_header_background if is_header else (
                    self.theme.table_alt_background if row_index % 2 else self.theme.table_row_background
                )
                if row_index == 0 and row_index == last_row_index:
                    draw.rounded_rectangle((x, row_top, x + width, row_bottom), radius=radius, fill=fill)
                elif row_index == 0:
                    draw.rounded_rectangle((x, row_top, x + width, row_bottom), radius=radius, fill=fill)
                    draw.rectangle((x, row_top + radius, x + width, row_bottom), fill=fill)
                elif row_index == last_row_index:
                    draw.rounded_rectangle((x, row_top, x + width, row_bottom), radius=radius, fill=fill)
                    draw.rectangle((x, row_top, x + width, row_bottom - radius), fill=fill)
                else:
                    draw.rectangle((x, row_top, x + width, row_bottom), fill=fill)

                cell_cursor_x = x
                for cell_index, lines in enumerate(rendered_cells):
                    cell_width = column_widths[cell_index]
                    cell_x = cell_cursor_x
                    if cell_index > 0:
                        draw.line(
                            (cell_x, row_top, cell_x, row_bottom),
                            fill=self.theme.border,
                            width=1,
                        )
                    self._draw_lines(
                        image,
                        lines,
                        x=cell_x + cell_pad_x,
                        y=row_top + cell_pad_y,
                        color=self.theme.foreground,
                    )
                    cell_cursor_x += cell_width
                if row_index < last_row_index:
                    draw.line((x, row_bottom, x + width, row_bottom), fill=self.theme.border, width=1)
                cursor_y = row_bottom + gap
        else:
            cursor_y = y + total_height
        return cursor_y + int(16 * self.scale)

    def _block_trailing_margin(self, block: BlockNode) -> int:
        if isinstance(block, Heading):
            return int(24 * self.scale)
        if isinstance(block, Paragraph):
            return int(18 * self.scale)
        if isinstance(block, Quote):
            return int(18 * self.scale)
        if isinstance(block, ListBlock):
            return int(8 * self.scale)
        if isinstance(block, CodeBlock):
            return int(18 * self.scale)
        if isinstance(block, TableBlock):
            return int(16 * self.scale)
        if isinstance(block, MathBlock):
            return int(20 * self.scale)
        if isinstance(block, ImageBlock):
            return int(14 * self.scale) if block.alt else int(18 * self.scale)
        return 0

    def _table_column_widths(self, block: TableBlock, *, total_width: int, min_width: int) -> list[int]:
        column_count = max(
            len(block.headers),
            max((len(row) for row in block.rows), default=0),
        )
        if column_count <= 0:
            return []
        weights = [1.0] * column_count

        def _update(cell: list[InlineNode], idx: int) -> None:
            text = self._inline_text_content(cell)
            visual = max(6, len(text))
            weights[idx] = max(weights[idx], math.sqrt(float(visual)))

        for idx, cell in enumerate(block.headers):
            _update(cell, idx)
        for row in block.rows:
            for idx, cell in enumerate(row[:column_count]):
                _update(cell, idx)

        available = max(total_width, min_width * column_count)
        scale = available / sum(weights)
        widths = [max(min_width, int(round(weight * scale))) for weight in weights]
        current = sum(widths)
        if current < available:
            widths[-1] += available - current
        elif current > available:
            overflow = current - available
            for idx in reversed(range(column_count)):
                take = min(overflow, max(0, widths[idx] - min_width))
                widths[idx] -= take
                overflow -= take
                if overflow <= 0:
                    break
        return widths

    def _render_code_block(self, block: CodeBlock, *, image: Image.Image | None, x: int, y: int, width: int) -> int:
        rendered = self._measure_code_block(block, width=width)
        if image is not None:
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle(
                (x, y, x + width, y + rendered.height),
                radius=max(8, int(10 * self.scale)),
                fill=self.theme.code_background,
            )
            if rendered.header_height > 0:
                header_bottom = y + rendered.header_height
                draw.rounded_rectangle(
                    (x, y, x + width, header_bottom),
                    radius=max(8, int(10 * self.scale)),
                    fill=self.theme.subtle,
                )
                draw.rectangle(
                    (x, y + rendered.header_height // 2, x + width, header_bottom),
                    fill=self.theme.subtle,
                )
                draw.line(
                    (x + int(14 * self.scale), header_bottom, x + width - int(14 * self.scale), header_bottom),
                    fill=self.theme.border,
                    width=max(1, int(2 * self.scale)),
                )
                if rendered.language_label:
                    label_font = self._font(max(12, int(self.fonts.code * 0.72)), role="mono", bold=True)
                    label_width = self._text_width(label_font, rendered.language_label)
                    pill_pad_x = int(10 * self.scale)
                    pill_height = self._font_metrics(label_font)[0] + self._font_metrics(label_font)[1] + int(8 * self.scale)
                    pill_width = label_width + pill_pad_x * 2
                    pill_right = x + width - int(18 * self.scale)
                    pill_left = pill_right - pill_width
                    pill_top = y + max(int(8 * self.scale), (rendered.header_height - pill_height) // 2)
                    pill_bottom = pill_top + pill_height
                    draw.rounded_rectangle(
                        (pill_left, pill_top, pill_right, pill_bottom),
                        radius=max(6, int(8 * self.scale)),
                        fill=self.theme.code_background,
                    )
                    draw.text(
                        (pill_left + pill_pad_x, pill_top + int(4 * self.scale)),
                        rendered.language_label,
                        font=label_font,
                        fill=self.theme.muted,
                    )
            gutter_left = x + rendered.pad_x - int(6 * self.scale)
            gutter_right = x + rendered.pad_x + rendered.gutter_width + rendered.gutter_gap // 2
            draw.rounded_rectangle(
                (
                    gutter_left,
                    y + rendered.header_height + int(10 * self.scale),
                    gutter_right,
                    y + rendered.height - int(10 * self.scale),
                ),
                radius=max(6, int(8 * self.scale)),
                fill=self.theme.subtle,
            )
            separator_x = x + rendered.pad_x + rendered.gutter_width + rendered.gutter_gap // 2
            draw.line(
                (
                    separator_x,
                    y + rendered.header_height + rendered.pad_top // 2,
                    separator_x,
                    y + rendered.height - rendered.pad_bottom // 2,
                ),
                fill=self.theme.border,
                width=max(1, int(2 * self.scale)),
            )
            self._draw_code_lines(
                image,
                rendered.lines,
                rendered.line_numbers,
                gutter_x=x + rendered.pad_x,
                gutter_width=rendered.gutter_width,
                x=x + rendered.pad_x + rendered.gutter_width + rendered.gutter_gap,
                y=y + rendered.header_height + rendered.pad_top,
                color=self.theme.foreground,
            )
        return y + rendered.height + int(18 * self.scale)

    def _measure_code_block(self, block: CodeBlock, *, width: int) -> _RenderedCodeBlock:
        pad_x = int(18 * self.scale)
        pad_top = int(20 * self.scale)
        pad_bottom = int(13 * self.scale)
        language_label = str(block.language or "").strip().lower()
        header_height = int(34 * self.scale) if language_label else 0
        raw_code = str(block.code or "")
        line_count = max(1, len(raw_code.rstrip("\n").splitlines()) or 1)
        line_number_font = self._font(max(12, int(self.fonts.code * 0.72)), role="mono")
        gutter_width = self._text_width(line_number_font, "9" * len(str(line_count))) + int(14 * self.scale)
        gutter_gap = int(16 * self.scale)
        inner_width = max(120, width - pad_x * 2 - gutter_width - gutter_gap)
        lines, line_numbers = self._layout_code(raw_code, block.language, inner_width)
        height = self._lines_height(lines) + pad_top + pad_bottom + header_height
        return _RenderedCodeBlock(
            lines=lines,
            line_numbers=line_numbers,
            language_label=language_label,
            height=height,
            pad_top=pad_top,
            pad_bottom=pad_bottom,
            pad_x=pad_x,
            gutter_width=gutter_width,
            gutter_gap=gutter_gap,
            header_height=header_height,
        )

    def _render_rich_text_block(
        self,
        nodes: Sequence[InlineNode],
        *,
        image: Image.Image | None,
        x: int,
        y: int,
        width: int,
        font_size: int,
        color: str,
        spacing_after: int,
        role: str,
    ) -> int:
        lines = self._layout_inline_nodes(nodes, width=width, font_size=font_size, color=color, role=role)
        if image is not None:
            self._draw_lines(image, lines, x=x, y=y, color=color)
        return y + self._lines_height(lines) + spacing_after

    def _layout_inline_nodes(
        self,
        nodes: Sequence[InlineNode],
        *,
        width: int,
        font_size: int,
        color: str,
        role: str = "body",
    ) -> list[_Line]:
        runs: list[_Run | LineBreak] = []
        for node in nodes:
            if isinstance(node, LineBreak):
                runs.append(node)
                continue
            if isinstance(node, TextSpan):
                fill = self.theme.link if node.style.link else color
                for token in self._split_text_tokens(node.text):
                    if not token:
                        continue
                    use_bold = bool(node.style.bold) or role == "heading"
                    font = (
                        self._heading_font_for_text(token, font_size, bold=use_bold, italic=node.style.italic)
                        if role == "heading"
                        else self._font_for_text(token, font_size, bold=node.style.bold, italic=node.style.italic)
                    )
                    runs.append(
                        _Run(
                            kind="text",
                            text=token,
                            font=font,
                            fill=fill,
                            width=self._text_width(font, token),
                            height=self._font_metrics(font)[0] + self._font_metrics(font)[1],
                            underline=bool(node.style.link),
                            strike=node.style.strike,
                            is_space=token.isspace(),
                            ascent=self._font_metrics(font)[0],
                            descent=self._font_metrics(font)[1],
                        )
                    )
                continue
            if isinstance(node, CodeSpan):
                text = str(node.text or "")
                font = self._mono_or_text_font(text, max(12, int(font_size * 0.92)))
                runs.append(
                    _Run(
                        kind="code",
                        text=text,
                        font=font,
                        fill=self.theme.inline_code_foreground,
                        background=self.theme.inline_code_background,
                        width=self._text_width(font, text) + int(16 * self.scale),
                        height=self._font_metrics(font)[0] + self._font_metrics(font)[1] + int(10 * self.scale),
                        pad_x=int(8 * self.scale),
                        pad_y=int(5 * self.scale),
                        ascent=self._font_metrics(font)[0] + int(5 * self.scale),
                        descent=self._font_metrics(font)[1] + int(5 * self.scale),
                    )
                )
                continue
            if isinstance(node, MathSpan):
                rendered = self._render_math_image(node.latex, max(16, int(font_size * 1.04)), color, inline=True)
                if rendered is None:
                    font = (
                        self._heading_font_for_text(node.latex, max(12, int(font_size * 0.9)))
                        if role == "heading"
                        else self._font_for_text(node.latex, max(12, int(font_size * 0.9)))
                    )
                    fallback = self._latex_fallback_text(node.latex)
                    runs.append(
                        _Run(
                            kind="text",
                            text=fallback,
                            font=font,
                            fill=color,
                            width=self._text_width(font, fallback),
                            height=self._font_metrics(font)[0] + self._font_metrics(font)[1],
                            ascent=self._font_metrics(font)[0],
                            descent=self._font_metrics(font)[1],
                        )
                    )
                else:
                    runs.append(
                        _Run(
                            kind="image",
                            width=rendered.image.width,
                            height=rendered.image.height,
                            image=rendered.image,
                            ascent=rendered.ascent,
                            descent=rendered.descent,
                        )
                    )
                continue
            if isinstance(node, ImageSpan):
                loaded = self._load_image(node.source)
                if loaded is None:
                    text = node.alt or "[image]"
                    font = self._heading_font_for_text(text, font_size) if role == "heading" else self._font_for_text(text, font_size)
                    runs.append(
                        _Run(
                            kind="text",
                            text=text,
                            font=font,
                            fill=self.theme.muted,
                            width=self._text_width(font, text),
                            height=self._font_metrics(font)[0] + self._font_metrics(font)[1],
                            ascent=self._font_metrics(font)[0],
                            descent=self._font_metrics(font)[1],
                        )
                    )
                else:
                    target_height = int(font_size * 1.6)
                    target = self._scale_image(loaded, height=target_height)
                    runs.append(
                        _Run(
                            kind="image",
                            width=target.width,
                            height=target.height,
                            image=target,
                            ascent=max(1, int(target.height * 0.8)),
                            descent=max(0, target.height - max(1, int(target.height * 0.8))),
                        )
                    )
        default_font = self._default_font_for_nodes(nodes, font_size=font_size, role=role)
        default_ascent, default_descent = self._font_metrics(default_font)
        return self._wrap_runs(
            runs,
            width=width,
            default_height=default_ascent + default_descent,
            default_ascent=default_ascent,
            default_descent=default_descent,
        )

    def _wrap_runs(
        self,
        runs: Sequence[_Run | LineBreak],
        *,
        width: int,
        default_height: int,
        default_ascent: int,
        default_descent: int,
    ) -> list[_Line]:
        lines: list[_Line] = []
        current: list[_Run] = []
        current_width = 0
        current_height = default_height
        current_ascent = default_ascent
        current_descent = default_descent

        def _append_run(run: _Run) -> None:
            nonlocal current_width, current_height, current_ascent, current_descent
            current.append(run)
            current_width += run.width
            current_height = max(current_height, run.height)
            current_ascent = max(current_ascent, run.ascent)
            current_descent = max(current_descent, run.descent)

        def _flush() -> None:
            nonlocal current, current_width, current_height, current_ascent, current_descent
            if not current:
                lines.append(_Line(runs=[], width=0, height=current_height, ascent=current_ascent, descent=current_descent))
            else:
                lines.append(
                    _Line(
                        runs=current,
                        width=current_width,
                        height=current_height,
                        ascent=current_ascent,
                        descent=current_descent,
                    )
                )
            current = []
            current_width = 0
            current_height = default_height
            current_ascent = default_ascent
            current_descent = default_descent

        for raw_run in runs:
            if isinstance(raw_run, LineBreak):
                _flush()
                continue
            for run in self._split_run_to_fit(raw_run, width=width):
                if run.is_space and not current:
                    continue
                if current and current_width + run.width > width:
                    leading = self._leading_no_line_start_punctuation(run.text if run.kind in {"text", "code"} else "")
                    if leading:
                        _append_run(self._clone_run(run, leading))
                        remainder = run.text[len(leading):]
                        if not remainder:
                            continue
                        run = self._clone_run(run, remainder)
                    _flush()
                    if run.is_space:
                        continue
                _append_run(run)
        if current or not lines:
            _flush()
        return lines

    def _split_run_to_fit(self, run: _Run, *, width: int) -> Iterable[_Run]:
        if run.width <= width or run.kind not in {"text", "code"} or not run.text:
            yield run
            return
        text = run.text
        buffer = ""
        for char in text:
            candidate = buffer + char
            candidate_width = self._run_text_width(run, candidate)
            if buffer and candidate_width > width:
                if char in _NO_LINE_START_PUNCTUATION:
                    buffer = candidate
                    continue
                yield self._clone_run(run, buffer)
                buffer = char
            else:
                buffer = candidate
        if buffer:
            yield self._clone_run(run, buffer)

    @staticmethod
    def _leading_no_line_start_punctuation(text: str) -> str:
        chars: list[str] = []
        for ch in str(text or ""):
            if ch not in _NO_LINE_START_PUNCTUATION:
                break
            chars.append(ch)
        return "".join(chars)

    def _clone_run(self, run: _Run, text: str) -> _Run:
        width = self._run_text_width(run, text)
        height = run.height
        ascent = run.ascent
        descent = run.descent
        if run.kind == "code":
            if run.font is not None:
                font_ascent, font_descent = self._font_metrics(run.font)
                ascent = font_ascent + run.pad_y
                descent = font_descent + run.pad_y
                height = ascent + descent
                width += run.pad_x * 2
        return _Run(
            kind=run.kind,
            text=text,
            font=run.font,
            fill=run.fill,
            background=run.background,
            underline=run.underline,
            strike=run.strike,
            width=width,
            height=height,
            pad_x=run.pad_x,
            pad_y=run.pad_y,
            is_space=text.isspace(),
            ascent=ascent,
            descent=descent,
        )

    def _run_text_width(self, run: _Run, text: str) -> int:
        if not run.font:
            return 0
        return self._text_width(run.font, text)

    def _draw_lines(self, image: Image.Image, lines: Sequence[_Line], *, x: int, y: int, color: str) -> None:
        draw = ImageDraw.Draw(image)
        cursor_y = y
        line_gap = int(8 * self.scale)
        for line in lines:
            cursor_x = x
            baseline_y = cursor_y + line.ascent
            for run in line.runs:
                top = baseline_y - run.ascent
                if run.kind == "image" and run.image is not None:
                    image.paste(run.image, (cursor_x, top), run.image)
                elif run.font is not None:
                    if run.background:
                        draw.rounded_rectangle(
                            (cursor_x, top, cursor_x + run.width, top + run.height),
                            radius=max(4, int(6 * self.scale)),
                            fill=run.background,
                        )
                    text_x = cursor_x + run.pad_x
                    text_y = baseline_y - run.ascent + run.pad_y
                    draw.text((text_x, text_y), run.text, font=run.font, fill=run.fill or color)
                    if run.underline:
                        font_ascent, font_descent = self._font_metrics(run.font)
                        underline_y = text_y + font_ascent + max(1, font_descent // 3)
                        draw.line(
                            (text_x, underline_y, text_x + self._text_width(run.font, run.text), underline_y),
                            fill=run.fill or color,
                            width=max(1, int(2 * self.scale)),
                        )
                    if run.strike:
                        font_ascent, _ = self._font_metrics(run.font)
                        strike_y = text_y + max(1, int(font_ascent * 0.55))
                        draw.line(
                            (text_x, strike_y, text_x + self._text_width(run.font, run.text), strike_y),
                            fill=run.fill or color,
                            width=max(1, int(2 * self.scale)),
                        )
                cursor_x += run.width
            cursor_y += line.height + line_gap

    def _draw_code_lines(
        self,
        image: Image.Image,
        lines: Sequence[_Line],
        line_numbers: Sequence[str],
        *,
        gutter_x: int,
        gutter_width: int,
        x: int,
        y: int,
        color: str,
    ) -> None:
        draw = ImageDraw.Draw(image)
        cursor_y = y
        line_gap = int(8 * self.scale)
        number_font = self._font(max(12, int(self.fonts.code * 0.72)), role="mono")
        number_ascent, _ = self._font_metrics(number_font)
        for index, line in enumerate(lines):
            baseline_y = cursor_y + line.ascent
            label = str(line_numbers[index] or "") if index < len(line_numbers) else ""
            if label:
                label_width = self._text_width(number_font, label)
                draw.text(
                    (
                        gutter_x + max(0, gutter_width - label_width - int(4 * self.scale)),
                        baseline_y - number_ascent,
                    ),
                    label,
                    font=number_font,
                    fill=self.theme.muted,
                )
            cursor_x = x
            for run in line.runs:
                top = baseline_y - run.ascent
                if run.kind == "image" and run.image is not None:
                    image.paste(run.image, (cursor_x, top), run.image)
                elif run.font is not None:
                    if run.background:
                        draw.rounded_rectangle(
                            (cursor_x, top, cursor_x + run.width, top + run.height),
                            radius=max(4, int(6 * self.scale)),
                            fill=run.background,
                        )
                    text_x = cursor_x + run.pad_x
                    text_y = baseline_y - run.ascent + run.pad_y
                    draw.text((text_x, text_y), run.text, font=run.font, fill=run.fill or color)
                    if run.underline:
                        font_ascent, font_descent = self._font_metrics(run.font)
                        underline_y = text_y + font_ascent + max(1, font_descent // 3)
                        draw.line(
                            (text_x, underline_y, text_x + self._text_width(run.font, run.text), underline_y),
                            fill=run.fill or color,
                            width=max(1, int(2 * self.scale)),
                        )
                    if run.strike:
                        font_ascent, _ = self._font_metrics(run.font)
                        strike_y = text_y + max(1, int(font_ascent * 0.55))
                        draw.line(
                            (text_x, strike_y, text_x + self._text_width(run.font, run.text), strike_y),
                            fill=run.fill or color,
                            width=max(1, int(2 * self.scale)),
                        )
                cursor_x += run.width
            cursor_y += line.height + line_gap

    def _lines_height(self, lines: Sequence[_Line]) -> int:
        if not lines:
            return 0
        gap = int(8 * self.scale)
        return sum(line.height for line in lines) + gap * max(0, len(lines) - 1)

    def _layout_code(self, code: str, language: str, width: int) -> tuple[list[_Line], list[str]]:
        lexer = self._code_lexer(language)
        style = get_style_by_name(self.theme.code_style)
        mono_font = self._mono_font(self.fonts.code)
        mono_ascent, mono_descent = self._font_metrics(mono_font)
        raw_lines: list[list[_Run]] = [[]]
        for token_type, value in lex(code or "", lexer):
            style_info = self._style_for_token(style, token_type)
            fill = "#" + style_info["color"] if style_info.get("color") else self.theme.foreground
            use_bold = bool(style_info.get("bold"))
            use_italic = bool(style_info.get("italic"))
            chunks = value.splitlines(keepends=True)
            for chunk in chunks:
                if chunk.endswith("\n"):
                    text = chunk[:-1]
                    if text:
                        font = self._mono_or_text_font(text, self.fonts.code, bold=use_bold, italic=use_italic)
                        raw_lines[-1].append(
                            _Run(
                                kind="text",
                                text=text,
                                font=font,
                                fill=fill,
                                width=self._text_width(font, text),
                                height=self._font_metrics(font)[0] + self._font_metrics(font)[1],
                                ascent=self._font_metrics(font)[0],
                                descent=self._font_metrics(font)[1],
                            )
                        )
                    raw_lines.append([])
                elif chunk:
                    font = self._mono_or_text_font(chunk, self.fonts.code, bold=use_bold, italic=use_italic)
                    raw_lines[-1].append(
                        _Run(
                            kind="text",
                            text=chunk,
                            font=font,
                            fill=fill,
                            width=self._text_width(font, chunk),
                            height=self._font_metrics(font)[0] + self._font_metrics(font)[1],
                            ascent=self._font_metrics(font)[0],
                            descent=self._font_metrics(font)[1],
                        )
                    )
        if len(raw_lines) > 1 and not raw_lines[-1] and str(code or "").endswith("\n"):
            raw_lines.pop()
        lines: list[_Line] = []
        line_numbers: list[str] = []
        for line_index, raw in enumerate(raw_lines, start=1):
            if not raw:
                lines.append(_Line(runs=[], width=0, height=mono_ascent + mono_descent, ascent=mono_ascent, descent=mono_descent))
                line_numbers.append(str(line_index))
                continue
            merged: list[_Run] = []
            for run in raw:
                merged.extend(self._split_run_to_fit(run, width=width))
            wrapped = self._wrap_runs(
                merged,
                width=width,
                default_height=mono_ascent + mono_descent,
                default_ascent=mono_ascent,
                default_descent=mono_descent,
            )
            lines.extend(wrapped)
            line_numbers.append(str(line_index))
            line_numbers.extend("" for _ in range(max(0, len(wrapped) - 1)))
        return lines, line_numbers

    @staticmethod
    def _style_for_token(style: Any, token_type: Any) -> dict[str, Any]:
        current = token_type
        while current is not None:
            try:
                return style.style_for_token(current)
            except KeyError:
                parent = getattr(current, "parent", None)
                if parent is None or parent == current:
                    break
                current = parent
        return {
            "color": "",
            "bold": False,
            "italic": False,
            "underline": False,
            "bgcolor": "",
            "border": "",
            "roman": None,
            "sans": None,
            "mono": None,
            "ansicolor": None,
        }

    @staticmethod
    def _code_lexer(language: str):
        lang = str(language or "").strip()
        if not lang:
            return TextLexer()
        try:
            return get_lexer_by_name(lang)
        except Exception:
            return TextLexer()

    def _render_math_image(self, latex: str, font_size: int, color: str, *, inline: bool = True) -> _MathRender | None:
        key = (str(latex or ""), int(font_size), color, bool(inline))
        if key in self._math_cache:
            return self._math_cache[key]
        if not key[0]:
            return None
        try:
            image = self._render_math_variant(key[0], font_size, color, inline=inline)
        except Exception:
            self._math_cache[key] = None
            return None
        self._math_cache[key] = image
        return image

    def _load_image(self, source: str) -> Image.Image | None:
        key = str(source or "").strip()
        if not key:
            return None
        if key in self._image_cache:
            return self._image_cache[key]
        image: Image.Image | None = None
        try:
            match = _DATA_IMAGE_RE.match(key)
            if match:
                image = Image.open(io.BytesIO(base64.b64decode(match.group(2)))).convert("RGBA")
            elif key.startswith(("http://", "https://")):
                response = httpx.get(key, timeout=15.0)
                response.raise_for_status()
                image = Image.open(io.BytesIO(response.content)).convert("RGBA")
            else:
                path = Path(key).expanduser()
                if path.is_file():
                    image = Image.open(path).convert("RGBA")
        except Exception:
            image = None
        self._image_cache[key] = image
        return image

    def _scale_image(
        self,
        image: Image.Image,
        *,
        width: int | None = None,
        height: int | None = None,
        max_height: int | None = None,
    ) -> Image.Image:
        src = image.copy()
        if width is None and height is None and max_height is None:
            return src
        target_width = src.width
        target_height = src.height
        if width is not None and src.width > width:
            ratio = width / float(src.width)
            target_width = int(src.width * ratio)
            target_height = int(src.height * ratio)
        if height is not None:
            ratio = height / float(src.height)
            target_width = int(src.width * ratio)
            target_height = int(src.height * ratio)
        if max_height is not None and target_height > max_height:
            ratio = max_height / float(target_height)
            target_width = int(target_width * ratio)
            target_height = int(target_height * ratio)
        target_width = max(1, target_width)
        target_height = max(1, target_height)
        if (target_width, target_height) == src.size:
            return src
        return src.resize((target_width, target_height), Image.Resampling.LANCZOS)

    def _text_width(self, font: ImageFont.ImageFont, text: str) -> int:
        if not text:
            return 0
        bbox = self._scratch_draw.textbbox((0, 0), text, font=font)
        return max(0, int(math.ceil(bbox[2] - bbox[0])))

    def _font_height(self, font: ImageFont.ImageFont | None) -> int:
        if font is None:
            return 0
        bbox = self._scratch_draw.textbbox((0, 0), "Hg", font=font)
        return max(1, int(math.ceil(bbox[3] - bbox[1])))

    def _font_metrics(self, font: ImageFont.ImageFont | None) -> tuple[int, int]:
        if font is None:
            return (0, 0)
        try:
            ascent, descent = font.getmetrics()
            return max(1, int(ascent)), max(0, int(descent))
        except Exception:
            height = self._font_height(font)
            return max(1, int(height * 0.8)), max(0, height - max(1, int(height * 0.8)))

    @staticmethod
    def _normalize_math_image(image: Image.Image, color: tuple[int, int, int]) -> tuple[Image.Image, tuple[int, int, int, int]] | None:
        alpha = image.convert("L")
        alpha = alpha.point(lambda value: 0 if value < 18 else min(255, int(pow(value / 255.0, 0.68) * 255)))
        bbox = alpha.getbbox()
        if not bbox:
            return None
        trimmed_alpha = alpha.crop(bbox)
        trimmed = Image.new("RGBA", trimmed_alpha.size, color + (0,))
        trimmed.putalpha(trimmed_alpha)
        return trimmed, tuple(int(value) for value in bbox)

    def _scale_math_render(self, rendered: _MathRender, ratio: float) -> _MathRender:
        if ratio <= 0:
            return rendered
        target_width = max(1, int(round(rendered.image.width * ratio)))
        target_height = max(1, int(round(rendered.image.height * ratio)))
        if (target_width, target_height) == rendered.image.size:
            return rendered
        scaled_image = rendered.image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        ascent = max(1, int(round(rendered.ascent * ratio)))
        ascent = min(ascent, target_height)
        descent = max(0, target_height - ascent)
        return _MathRender(image=scaled_image, ascent=ascent, descent=descent)

    def _inline_math_metric(self, rendered: _MathRender) -> float:
        visual_height = self._math_visual_height(rendered.image)
        return max(1.0, visual_height)

    @staticmethod
    def _block_math_metric(rendered: _MathRender) -> float:
        return max(1.0, PillowMarkdownRenderer._math_visual_height(rendered.image))

    def _normalize_math_render_size(
        self,
        rendered: _MathRender,
        *,
        font_size: int,
        reference_ascent: int,
        reference_descent: int,
        inline: bool,
    ) -> _MathRender:
        if inline:
            target_metric = max(22.0, float(reference_ascent) * 1.08)
            current_metric = self._inline_math_metric(rendered)
            normalized = self._scale_math_render(rendered, target_metric / current_metric)
            max_height = max(
                int(round(font_size * 2.35)),
                int(round(reference_ascent + reference_descent + max(16, reference_ascent * 1.45))),
            )
            if normalized.image.height > max_height:
                normalized = self._scale_math_render(normalized, max_height / float(normalized.image.height))
            return normalized

        target_metric = max(30.0, float(font_size) * 0.72)
        current_metric = self._block_math_metric(rendered)
        normalized = self._scale_math_render(rendered, target_metric / current_metric)
        max_height = max(int(round(font_size * 1.55)), int(round(target_metric * 1.6)))
        if normalized.image.height > max_height:
            normalized = self._scale_math_render(normalized, max_height / float(normalized.image.height))
        return normalized

    @staticmethod
    def _math_visual_height(image: Image.Image) -> float:
        alpha = image.getchannel("A")
        row_sums = [sum(alpha.getpixel((x, y)) for x in range(alpha.width)) for y in range(alpha.height)]
        if not row_sums:
            return 1.0
        max_row = max(row_sums)
        if max_row <= 0:
            return float(image.height)

        def _band_height(threshold: float) -> int:
            active = [index for index, value in enumerate(row_sums) if value >= max_row * threshold]
            if not active:
                return 0
            return active[-1] - active[0] + 1

        dense_band = _band_height(0.35)
        visual = dense_band + image.height * 0.15
        return max(1.0, float(visual or image.height))

    def _render_math_variant(self, latex: str, font_size: int, color: str, *, inline: bool) -> _MathRender | None:
        try:
            from matplotlib.font_manager import FontProperties
            from matplotlib.mathtext import MathTextParser
            from matplotlib import rc_context
        except Exception:
            return None
        variants = self._latex_variants(latex)
        parser = MathTextParser("agg")
        rgb = self._hex_to_rgb(color)
        reference_font = self._font(max(12, int(font_size)))
        reference_ascent, reference_descent = self._font_metrics(reference_font)
        for variant in variants:
            try:
                if "\\begin{cases}" in variant:
                    cases_render = self._render_cases_math(
                        variant,
                        font_size,
                        color,
                        inline=inline,
                        parser=parser,
                    )
                    if cases_render is not None:
                        return self._normalize_math_render_size(
                            cases_render,
                            font_size=font_size,
                            reference_ascent=reference_ascent,
                            reference_descent=reference_descent,
                            inline=inline,
                        )
                    continue

                with rc_context({"mathtext.fontset": "stix", "mathtext.default": "it"}):
                    parsed = parser.parse(
                        f"${variant}$",
                        dpi=220 if inline else 240,
                        prop=FontProperties(size=max(10, int(font_size))),
                        antialiased=True,
                    )
                gray = Image.frombytes(
                    "L",
                    (max(1, int(math.ceil(parsed.width))), max(1, int(math.ceil(parsed.height)))),
                    bytes(parsed.image),
                )
                normalized = self._normalize_math_image(gray, rgb)
                if normalized is None:
                    continue
                image, bbox = normalized
                crop_top = bbox[1]
                raw_height = max(1, gray.height)
                raw_baseline = raw_height - max(0.0, float(getattr(parsed, "depth", 0.0)))
                trimmed_ascent = max(1.0, raw_baseline - crop_top)
                trimmed_descent = max(0.0, image.height - trimmed_ascent)
                ascent = max(1, min(image.height, int(round(trimmed_ascent))))
                math_render = _MathRender(
                    image=image,
                    ascent=ascent,
                    descent=max(0, image.height - ascent),
                )
                return self._normalize_math_render_size(
                    math_render,
                    font_size=font_size,
                    reference_ascent=reference_ascent,
                    reference_descent=reference_descent,
                    inline=inline,
                )
            except Exception:
                continue
        return None

    def _render_cases_math(
        self,
        latex: str,
        font_size: int,
        color: str,
        *,
        inline: bool,
        parser: Any,
    ) -> _MathRender | None:
        match = re.match(
            r"^(?P<prefix>.*?)\\begin\{cases\}(?P<body>.*?)\\end\{cases\}$",
            str(latex or "").strip(),
            flags=re.DOTALL,
        )
        if not match:
            return None

        prefix = str(match.group("prefix") or "").strip()
        body = str(match.group("body") or "").strip()
        rows = [row.strip() for row in re.split(r"\\\\", body) if str(row or "").strip()]
        if not rows:
            return None

        prefix_render = self._render_math_fragment(prefix, font_size, color, parser=parser, inline=True) if prefix else None
        brace_render = self._render_math_fragment(r"\{", max(font_size, int(font_size * 1.6)), color, parser=parser, inline=True)

        rendered_rows: list[tuple[_MathRender | None, _MathRender | None]] = []
        left_width = 0
        right_width = 0
        row_heights: list[int] = []
        for row in rows:
            left_text, _, right_text = row.partition("&")
            left_render = self._render_math_fragment(left_text.strip(), max(16, int(font_size * 0.88)), color, parser=parser, inline=True)
            right_render = self._render_math_fragment(right_text.strip(), max(16, int(font_size * 0.88)), color, parser=parser, inline=True)
            rendered_rows.append((left_render, right_render))
            if left_render is not None:
                left_width = max(left_width, left_render.image.width)
            if right_render is not None:
                right_width = max(right_width, right_render.image.width)
            row_heights.append(max(left_render.image.height if left_render else 0, right_render.image.height if right_render else 0, max(18, int(font_size * 0.72))))

        gap_x = int(12 * self.scale)
        gap_y = int(8 * self.scale)
        rows_height = sum(row_heights) + gap_y * max(0, len(row_heights) - 1)
        brace_target_height = max(rows_height + int(6 * self.scale), brace_render.image.height if brace_render else rows_height)
        if brace_render is not None and brace_render.image.height > 0:
            brace_render = self._scale_math_render(brace_render, brace_target_height / float(brace_render.image.height))

        prefix_gap = int(16 * self.scale) if prefix_render is not None else 0
        total_width = (
            (prefix_render.image.width if prefix_render is not None else 0)
            + prefix_gap
            + (brace_render.image.width if brace_render is not None else 0)
            + gap_x
            + left_width
            + gap_x
            + right_width
        )
        total_height = max(
            rows_height,
            prefix_render.image.height if prefix_render is not None else 0,
            brace_render.image.height if brace_render is not None else 0,
        )
        canvas = Image.new("RGBA", (max(1, total_width), max(1, total_height)), (255, 255, 255, 0))

        cursor_x = 0
        if prefix_render is not None:
            prefix_y = max(0, (total_height - prefix_render.image.height) // 2)
            canvas.paste(prefix_render.image, (cursor_x, prefix_y), prefix_render.image)
            cursor_x += prefix_render.image.width + prefix_gap

        if brace_render is not None:
            brace_y = max(0, (total_height - brace_render.image.height) // 2)
            canvas.paste(brace_render.image, (cursor_x, brace_y), brace_render.image)
            cursor_x += brace_render.image.width + gap_x

        rows_x = cursor_x
        row_y = max(0, (total_height - rows_height) // 2)
        for (left_render, right_render), row_height in zip(rendered_rows, row_heights, strict=False):
            if left_render is not None:
                left_y = row_y + max(0, (row_height - left_render.image.height) // 2)
                canvas.paste(left_render.image, (rows_x + left_width - left_render.image.width, left_y), left_render.image)
            if right_render is not None:
                right_y = row_y + max(0, (row_height - right_render.image.height) // 2)
                canvas.paste(right_render.image, (rows_x + left_width + gap_x, right_y), right_render.image)
            row_y += row_height + gap_y

        alpha = canvas.getchannel("A")
        bbox = alpha.getbbox()
        if not bbox:
            return None
        image = canvas.crop(bbox)
        return _MathRender(
            image=image,
            ascent=max(1, int(round(image.height * 0.78))),
            descent=max(0, image.height - max(1, int(round(image.height * 0.78)))),
        )

    def _render_math_fragment(
        self,
        latex: str,
        font_size: int,
        color: str,
        *,
        parser: Any,
        inline: bool,
    ) -> _MathRender | None:
        try:
            from matplotlib.font_manager import FontProperties
            from matplotlib import rc_context
        except Exception:
            return None

        text = str(latex or "").strip()
        if not text:
            return None
        sanitized = text
        for pattern, replacement in _LATEX_SANITIZE_RULES:
            sanitized = pattern.sub(replacement, sanitized)

        rgb = self._hex_to_rgb(color)
        try:
            with rc_context({"mathtext.fontset": "stix", "mathtext.default": "it"}):
                parsed = parser.parse(
                    f"${sanitized}$",
                    dpi=220 if inline else 240,
                    prop=FontProperties(size=max(10, int(font_size))),
                    antialiased=True,
                )
            gray = Image.frombytes(
                "L",
                (max(1, int(math.ceil(parsed.width))), max(1, int(math.ceil(parsed.height)))),
                bytes(parsed.image),
            )
        except Exception:
            return None

        normalized = self._normalize_math_image(gray, rgb)
        if normalized is None:
            return None
        image, bbox = normalized
        crop_top = bbox[1]
        raw_height = max(1, gray.height)
        raw_baseline = raw_height - max(0.0, float(getattr(parsed, "depth", 0.0)))
        trimmed_ascent = max(1.0, raw_baseline - crop_top)
        ascent = max(1, min(image.height, int(round(trimmed_ascent))))
        return _MathRender(
            image=image,
            ascent=ascent,
            descent=max(0, image.height - ascent),
        )

    @staticmethod
    def _latex_variants(latex: str) -> list[str]:
        raw = str(latex or "").strip()
        if not raw:
            return []
        variants = [raw]
        sanitized = raw
        for pattern, replacement in _LATEX_SANITIZE_RULES:
            sanitized = pattern.sub(replacement, sanitized)
        if sanitized != raw:
            variants.append(sanitized)
        return variants

    @staticmethod
    def _latex_fallback_text(latex: str) -> str:
        text = str(latex or "").strip()
        text = re.sub(r"\\[a-zA-Z]+\{([^}]+)\}", r"\1", text)
        text = re.sub(r"\\([a-zA-Z]+)", r"\1", text)
        text = text.replace("{", "").replace("}", "")
        text = text.replace("^", "")
        text = text.replace("_", "")
        return text or "[math]"

    @staticmethod
    def _hex_to_rgb(color: str) -> tuple[int, int, int]:
        text = str(color or "").strip().lstrip("#")
        if len(text) == 6:
            try:
                return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
            except Exception:
                pass
        return (31, 41, 51)

    def _default_font_for_nodes(self, nodes: Sequence[InlineNode], *, font_size: int, role: str) -> ImageFont.ImageFont:
        sample_text = self._inline_text_content(nodes)
        if role == "heading":
            return self._heading_font_for_text(sample_text, font_size, bold=True)
        return self._font(font_size, role=self._script_bucket_for_text(sample_text), bold=False, italic=False)

    def _font(self, size: int, *, role: str = "sans", bold: bool = False, italic: bool = False) -> ImageFont.ImageFont:
        entry = self._primary_fonts.get(("body", role, bool(bold), bool(italic)))
        if entry is not None:
            return self._font_registry.font_from_entry(entry, max(12, int(size)))
        return self._font_registry.font_for_text("", size=max(12, int(size)), role=role, bold=bold, italic=italic)

    def _mono_font(self, size: int, *, bold: bool = False, italic: bool = False) -> ImageFont.ImageFont:
        entry = self._primary_fonts.get(("code", "mono", bool(bold), bool(italic)))
        if entry is not None:
            return self._font_registry.font_from_entry(entry, max(12, int(size)))
        return self._font_registry.font_for_text("", size=max(12, int(size)), role="mono", bold=bold, italic=italic)

    def _font_for_text(self, text: str, size: int, *, bold: bool = False, italic: bool = False) -> ImageFont.ImageFont:
        role = self._script_bucket_for_text(text)
        entry = self._primary_fonts.get(("body", role, bool(bold), bool(italic)))
        if self._font_registry.text_covered_by_entry(entry, text):
            return self._font_registry.font_from_entry(entry, max(12, int(size)))
        return self._font_registry.font_for_text(text, size=max(12, int(size)), role=role, bold=bold, italic=italic)

    def _heading_font_for_text(self, text: str, size: int, *, bold: bool = False, italic: bool = False) -> ImageFont.ImageFont:
        role = self._script_bucket_for_text(text)
        entry = self._primary_fonts.get(("heading", role, bool(bold), bool(italic)))
        if self._font_registry.text_covered_by_entry(entry, text):
            return self._font_registry.font_from_entry(entry, max(12, int(size)))
        return self._font_registry.font_for_text(text, size=max(12, int(size)), role=role, bold=bold, italic=italic)

    def _mono_or_text_font(self, text: str, size: int, *, bold: bool = False, italic: bool = False) -> ImageFont.ImageFont:
        entry = self._primary_fonts.get(("code", "mono", bool(bold), bool(italic)))
        if self._font_registry.text_covered_by_entry(entry, text):
            return self._font_registry.font_from_entry(entry, max(12, int(size)))
        return self._font_registry.font_for_text(text, size=max(12, int(size)), role="mono", bold=bold, italic=italic)

    @staticmethod
    def _split_text_tokens(text: str) -> list[str]:
        parts: list[str] = []
        for chunk in re.split(r"(\s+)", str(text or "")):
            if not chunk:
                continue
            if chunk.isspace():
                parts.append(chunk)
                continue
            dominant_cjk_role = _resolved_role(chunk, "sans") if any(_is_cjk(ch) for ch in chunk) else "sans"
            buffer = chunk[0]
            current_role = dominant_cjk_role if _is_cjk(chunk[0]) and dominant_cjk_role.startswith("cjk_") else _resolved_role(chunk[0], "sans")
            for ch in chunk[1:]:
                ch_role = dominant_cjk_role if _is_cjk(ch) and dominant_cjk_role.startswith("cjk_") else _resolved_role(ch, "sans")
                if ch_role == current_role:
                    buffer += ch
                    continue
                parts.append(buffer)
                buffer = ch
                current_role = ch_role
            if buffer:
                parts.append(buffer)
        return parts

    @staticmethod
    def _inline_text_content(nodes: Sequence[InlineNode]) -> str:
        parts: list[str] = []
        for node in nodes:
            if isinstance(node, TextSpan):
                parts.append(node.text)
            elif isinstance(node, CodeSpan):
                parts.append(node.text)
            elif isinstance(node, MathSpan):
                parts.append(node.latex)
            elif isinstance(node, ImageSpan):
                parts.append(node.alt or "[image]")
            elif isinstance(node, LineBreak):
                parts.append(" ")
        return " ".join(part.strip() for part in parts if str(part).strip())

def _is_cjk(ch: str) -> bool:
    if not ch:
        return False
    code = ord(ch)
    if 0x3040 <= code <= 0x30FF:
        return True
    if 0x31F0 <= code <= 0x31FF:
        return True
    if 0x3400 <= code <= 0x9FFF:
        return True
    if 0xF900 <= code <= 0xFAFF:
        return True
    if 0xAC00 <= code <= 0xD7AF:
        return True
    return unicodedata.east_asian_width(ch) in {"W", "F"}


def _is_han(ch: str) -> bool:
    if not ch:
        return False
    code = ord(ch)
    return (0x3400 <= code <= 0x9FFF) or (0xF900 <= code <= 0xFAFF)


def render_markdown_image(
    markdown_text: str,
    *,
    title: str = "Markdown Render",
    theme: str = "paper",
    accent: str | None = None,
    width: int = DEFAULT_PAGE_WIDTH,
    padding: int = DEFAULT_PADDING,
    scale: float = DEFAULT_SCALE,
    font_paths: list[str] | None = None,
    font_dirs: list[str] | None = None,
    font_pack: str | None = None,
) -> RenderResult:
    renderer = PillowMarkdownRenderer(
        width=width,
        padding=padding,
        theme=theme,
        accent=accent,
        scale=scale,
        font_paths=font_paths,
        font_dirs=font_dirs,
        font_pack=font_pack,
    )
    return renderer.render_markdown(markdown_text, title=title)
