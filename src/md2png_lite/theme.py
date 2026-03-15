from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RenderTheme:
    name: str
    background: str
    foreground: str
    muted: str
    accent: str
    subtle: str
    border: str
    quote_background: str
    quote_border: str
    code_background: str
    code_border: str
    table_header_background: str
    table_row_background: str
    table_alt_background: str
    link: str
    inline_code_foreground: str
    inline_code_background: str
    code_style: str


_THEMES: dict[str, RenderTheme] = {
    "paper": RenderTheme(
        name="paper",
        background="#f5efe6",
        foreground="#1f2933",
        muted="#69707a",
        accent="#c46b2d",
        subtle="#ede4d6",
        border="#e5dbc9",
        quote_background="#fbf6ee",
        quote_border="#d97706",
        code_background="#f7f1e8",
        code_border="#f7f1e8",
        table_header_background="#efe2cf",
        table_row_background="#fcfaf6",
        table_alt_background="#f8f2e8",
        link="#0f766e",
        inline_code_foreground="#8b5e34",
        inline_code_background="#eee1cf",
        code_style="friendly",
    ),
    "github-light": RenderTheme(
        name="GitHub Light",
        background="#ffffff",
        foreground="#1f2328",
        muted="#656d76",
        accent="#0969da",
        subtle="#f6f8fa",
        border="#d0d7de",
        quote_background="#f6f8fa",
        quote_border="#d0d7de",
        code_background="#f6f8fa",
        code_border="#d0d7de",
        table_header_background="#f6f8fa",
        table_row_background="#ffffff",
        table_alt_background="#f6f8fa",
        link="#0969da",
        inline_code_foreground="#cf222e",
        inline_code_background="#f6f8fa",
        code_style="xcode",
    ),
    "github-dark": RenderTheme(
        name="GitHub Dark",
        background="#0d1117",
        foreground="#e6edf3",
        muted="#8b949e",
        accent="#2f81f7",
        subtle="#161b22",
        border="#30363d",
        quote_background="#11161d",
        quote_border="#3b82f6",
        code_background="#161b22",
        code_border="#30363d",
        table_header_background="#161b22",
        table_row_background="#0d1117",
        table_alt_background="#11161d",
        link="#58a6ff",
        inline_code_foreground="#ff7b72",
        inline_code_background="#1f2937",
        code_style="github-dark",
    ),
    "solarized-light": RenderTheme(
        name="Solarized Light",
        background="#fdf6e3",
        foreground="#586e75",
        muted="#93a1a1",
        accent="#cb4b16",
        subtle="#eee8d5",
        border="#e4dcc7",
        quote_background="#f7f1df",
        quote_border="#b58900",
        code_background="#f7f1df",
        code_border="#e4dcc7",
        table_header_background="#eee8d5",
        table_row_background="#fdf6e3",
        table_alt_background="#f7f1df",
        link="#268bd2",
        inline_code_foreground="#d33682",
        inline_code_background="#eee8d5",
        code_style="solarized-light",
    ),
    "graphite": RenderTheme(
        name="Graphite",
        background="#101418",
        foreground="#e5e7eb",
        muted="#9ca3af",
        accent="#f97316",
        subtle="#1b2430",
        border="#2c3948",
        quote_background="#141b23",
        quote_border="#fb923c",
        code_background="#0b1117",
        code_border="#334155",
        table_header_background="#18212c",
        table_row_background="#121922",
        table_alt_background="#0f151d",
        link="#38bdf8",
        inline_code_foreground="#fdba74",
        inline_code_background="#1b2430",
        code_style="monokai",
    ),
}

_THEME_ALIASES = {
    "阅读器": "paper",
    "reader": "paper",
    "github": "github-light",
    "github-day": "github-light",
    "github-white": "github-light",
    "solarized": "solarized-light",
}


def _resolve_theme_key(name: str | None) -> str:
    raw = str(name or "paper").strip()
    if not raw:
        return "paper"
    if raw in _THEMES:
        return raw
    lowered = raw.lower()
    if lowered in _THEMES:
        return lowered
    alias = _THEME_ALIASES.get(lowered)
    if alias:
        return alias
    return "paper"


def get_theme(name: str | None = None, *, accent: str | None = None) -> RenderTheme:
    base = _THEMES[_resolve_theme_key(name)]
    if not accent:
        return base
    return RenderTheme(
        name=base.name,
        background=base.background,
        foreground=base.foreground,
        muted=base.muted,
        accent=accent,
        subtle=base.subtle,
        border=base.border,
        quote_background=base.quote_background,
        quote_border=accent,
        code_background=base.code_background,
        code_border=base.code_border,
        table_header_background=base.table_header_background,
        table_row_background=base.table_row_background,
        table_alt_background=base.table_alt_background,
        link=accent,
        inline_code_foreground=base.inline_code_foreground,
        inline_code_background=base.inline_code_background,
        code_style=base.code_style,
    )


def list_themes() -> list[str]:
    return list(_THEMES)
