from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias


@dataclass(frozen=True)
class TextStyleState:
    bold: bool = False
    italic: bool = False
    strike: bool = False
    link: str = ""


@dataclass(frozen=True)
class TextSpan:
    text: str
    style: TextStyleState = field(default_factory=TextStyleState)


@dataclass(frozen=True)
class CodeSpan:
    text: str


@dataclass(frozen=True)
class MathSpan:
    latex: str


@dataclass(frozen=True)
class ImageSpan:
    source: str
    alt: str = ""


@dataclass(frozen=True)
class LineBreak:
    hard: bool = False


InlineNode: TypeAlias = TextSpan | CodeSpan | MathSpan | ImageSpan | LineBreak


@dataclass(frozen=True)
class Paragraph:
    children: list[InlineNode]


@dataclass(frozen=True)
class Heading:
    level: int
    children: list[InlineNode]


@dataclass(frozen=True)
class Quote:
    children: list["BlockNode"]


@dataclass(frozen=True)
class ListItem:
    children: list["BlockNode"]


@dataclass(frozen=True)
class ListBlock:
    ordered: bool
    items: list[ListItem]
    start: int = 1


@dataclass(frozen=True)
class Rule:
    pass


@dataclass(frozen=True)
class CodeBlock:
    code: str
    language: str = ""


@dataclass(frozen=True)
class MathBlock:
    latex: str


@dataclass(frozen=True)
class ImageBlock:
    source: str
    alt: str = ""


@dataclass(frozen=True)
class TableBlock:
    headers: list[list[InlineNode]]
    rows: list[list[list[InlineNode]]]


BlockNode: TypeAlias = Paragraph | Heading | Quote | ListBlock | Rule | CodeBlock | MathBlock | ImageBlock | TableBlock


@dataclass(frozen=True)
class Document:
    children: list[BlockNode]
