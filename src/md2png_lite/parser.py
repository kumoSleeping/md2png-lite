from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins.dollarmath import dollarmath_plugin

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
    TextStyleState,
)


class MarkdownDocumentParser:
    def __init__(self) -> None:
        self._md = MarkdownIt("commonmark", {"breaks": True, "html": False}).enable(
            ["table", "strikethrough"]
        )
        self._md.use(dollarmath_plugin)

    def parse(self, text: str) -> Document:
        tokens = self._md.parse(str(text or ""))
        children, _ = self._parse_blocks(tokens, 0)
        return Document(children=children)

    def _parse_blocks(
        self,
        tokens: Sequence[Token],
        index: int,
        stop_types: set[str] | None = None,
    ) -> tuple[list[BlockNode], int]:
        blocks: list[BlockNode] = []
        stop = stop_types or set()
        i = index
        while i < len(tokens):
            token = tokens[i]
            if token.type in stop:
                return blocks, i + 1
            if token.type == "paragraph_open":
                block, i = self._parse_paragraph(tokens, i)
                blocks.append(block)
                continue
            if token.type == "heading_open":
                block, i = self._parse_heading(tokens, i)
                blocks.append(block)
                continue
            if token.type == "blockquote_open":
                child_blocks, i = self._parse_blocks(tokens, i + 1, {"blockquote_close"})
                blocks.append(Quote(children=child_blocks))
                continue
            if token.type == "bullet_list_open":
                block, i = self._parse_list(tokens, i, ordered=False)
                blocks.append(block)
                continue
            if token.type == "ordered_list_open":
                block, i = self._parse_list(tokens, i, ordered=True)
                blocks.append(block)
                continue
            if token.type in {"fence", "code_block"}:
                language = str((token.info or "").strip().split()[0] if token.info else "")
                blocks.append(CodeBlock(code=str(token.content or ""), language=language))
                i += 1
                continue
            if token.type == "math_block":
                blocks.append(MathBlock(latex=str(token.content or "").strip()))
                i += 1
                continue
            if token.type == "hr":
                blocks.append(Rule())
                i += 1
                continue
            if token.type == "table_open":
                block, i = self._parse_table(tokens, i)
                blocks.append(block)
                continue
            if token.type == "inline":
                inlines = self._parse_inline(token.children or [])
                blocks.append(self._paragraph_or_image(inlines))
                i += 1
                continue
            if token.type in {"html_block", "html_inline"}:
                text = str(token.content or "").strip()
                if text:
                    blocks.append(Paragraph(children=[TextSpan(text=text)]))
                i += 1
                continue
            i += 1
        return blocks, i

    def _parse_paragraph(self, tokens: Sequence[Token], index: int) -> tuple[BlockNode, int]:
        i = index + 1
        children: list[InlineNode] = []
        while i < len(tokens) and tokens[i].type != "paragraph_close":
            token = tokens[i]
            if token.type == "inline":
                children.extend(self._parse_inline(token.children or []))
            elif token.type == "image":
                children.append(
                    ImageSpan(
                        source=str(token.attrGet("src") or "").strip(),
                        alt=str(token.content or token.attrGet("alt") or "").strip(),
                    )
                )
            i += 1
        return self._paragraph_or_image(children), min(i + 1, len(tokens))

    def _parse_heading(self, tokens: Sequence[Token], index: int) -> tuple[Heading, int]:
        token = tokens[index]
        level = int(str(token.tag or "h1")[1:] or 1)
        i = index + 1
        children: list[InlineNode] = []
        while i < len(tokens) and tokens[i].type != "heading_close":
            if tokens[i].type == "inline":
                children.extend(self._parse_inline(tokens[i].children or []))
            i += 1
        return Heading(level=level, children=children), min(i + 1, len(tokens))

    def _parse_list(
        self,
        tokens: Sequence[Token],
        index: int,
        *,
        ordered: bool,
    ) -> tuple[ListBlock, int]:
        token = tokens[index]
        start = 1
        if ordered:
            try:
                start = int(str(token.attrGet("start") or "1").strip())
            except Exception:
                start = 1
        end_type = "ordered_list_close" if ordered else "bullet_list_close"
        items: list[ListItem] = []
        i = index + 1
        while i < len(tokens):
            if tokens[i].type == end_type:
                return ListBlock(ordered=ordered, items=items, start=start), i + 1
            if tokens[i].type == "list_item_open":
                child_blocks, i = self._parse_blocks(tokens, i + 1, {"list_item_close"})
                items.append(ListItem(children=child_blocks))
                continue
            i += 1
        return ListBlock(ordered=ordered, items=items, start=start), i

    def _parse_table(self, tokens: Sequence[Token], index: int) -> tuple[TableBlock, int]:
        headers: list[list[InlineNode]] = []
        rows: list[list[list[InlineNode]]] = []
        in_head = False
        i = index + 1
        while i < len(tokens):
            token = tokens[i]
            if token.type == "table_close":
                return TableBlock(headers=headers, rows=rows), i + 1
            if token.type == "thead_open":
                in_head = True
                i += 1
                continue
            if token.type == "thead_close":
                in_head = False
                i += 1
                continue
            if token.type == "tr_open":
                row: list[list[InlineNode]] = []
                i += 1
                while i < len(tokens) and tokens[i].type != "tr_close":
                    cell_token = tokens[i]
                    if cell_token.type in {"th_open", "td_open"}:
                        cell_close = "th_close" if cell_token.type == "th_open" else "td_close"
                        cell, i = self._parse_table_cell(tokens, i + 1, cell_close)
                        row.append(cell)
                        continue
                    i += 1
                if in_head:
                    headers = row
                elif row:
                    rows.append(row)
                i += 1
                continue
            i += 1
        return TableBlock(headers=headers, rows=rows), i

    def _parse_table_cell(
        self,
        tokens: Sequence[Token],
        index: int,
        close_type: str,
    ) -> tuple[list[InlineNode], int]:
        cell: list[InlineNode] = []
        i = index
        while i < len(tokens):
            token = tokens[i]
            if token.type == close_type:
                return cell, i + 1
            if token.type == "inline":
                cell.extend(self._parse_inline(token.children or []))
            elif token.type == "paragraph_open":
                paragraph, i = self._parse_paragraph(tokens, i)
                if isinstance(paragraph, Paragraph):
                    cell.extend(paragraph.children)
                elif isinstance(paragraph, ImageBlock):
                    cell.append(ImageSpan(source=paragraph.source, alt=paragraph.alt))
                continue
            i += 1
        return cell, i

    def _parse_inline(self, tokens: Sequence[Token]) -> list[InlineNode]:
        style = TextStyleState()
        stack: list[TextStyleState] = []
        items: list[InlineNode] = []
        for token in tokens:
            t = token.type
            if t == "text":
                content = str(token.content or "")
                if content:
                    items.append(TextSpan(text=content, style=style))
                continue
            if t == "softbreak":
                items.append(LineBreak(hard=False))
                continue
            if t == "hardbreak":
                items.append(LineBreak(hard=True))
                continue
            if t == "code_inline":
                items.append(CodeSpan(text=str(token.content or "")))
                continue
            if t == "math_inline":
                items.append(MathSpan(latex=str(token.content or "").strip()))
                continue
            if t == "image":
                items.append(
                    ImageSpan(
                        source=str(token.attrGet("src") or "").strip(),
                        alt=str(token.content or token.attrGet("alt") or "").strip(),
                    )
                )
                continue
            if t == "strong_open":
                stack.append(style)
                style = replace(style, bold=True)
                continue
            if t == "strong_close":
                style = stack.pop() if stack else TextStyleState()
                continue
            if t == "em_open":
                stack.append(style)
                style = replace(style, italic=True)
                continue
            if t == "em_close":
                style = stack.pop() if stack else TextStyleState()
                continue
            if t == "s_open":
                stack.append(style)
                style = replace(style, strike=True)
                continue
            if t == "s_close":
                style = stack.pop() if stack else TextStyleState()
                continue
            if t == "link_open":
                stack.append(style)
                style = replace(style, link=str(token.attrGet("href") or "").strip())
                continue
            if t == "link_close":
                style = stack.pop() if stack else TextStyleState()
                continue
        return items

    @staticmethod
    def _paragraph_or_image(children: list[InlineNode]) -> BlockNode:
        if len(children) == 1 and isinstance(children[0], ImageSpan):
            return ImageBlock(source=children[0].source, alt=children[0].alt)
        return Paragraph(children=children)


def parse_markdown_document(text: str) -> Document:
    return MarkdownDocumentParser().parse(text)
