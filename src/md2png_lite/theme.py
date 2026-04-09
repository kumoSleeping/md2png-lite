from __future__ import annotations

from dataclasses import dataclass, replace


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
    heading_accent: str
    heading_foreground: str
    summary_background: str
    summary_border: str
    summary_badge_background: str
    summary_badge_foreground: str
    default_width: int
    minimum_width: int
    default_padding: int
    default_scale: float
    body_font_base: int = 28
    code_font_base: int = 26
    quote_font_base: int = 26
    title_font_base: int = 18
    heading_font_bases: tuple[int, int, int, int, int, int] = (50, 42, 36, 32, 28, 26)
    heading_width_factors: tuple[float, float, float, float, float, float] = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
    body_line_gap_base: int = 8
    heading_line_gap_base: int = 8
    code_line_gap_base: int = 8
    heading_spacing_base: int = 24
    paragraph_spacing_base: int = 18
    quote_spacing_base: int = 18
    list_spacing_base: int = 8
    code_spacing_base: int = 18
    summary_spacing_base: int = 20
    table_spacing_base: int = 16
    image_spacing_base: int = 18
    list_inset_base: int = 18
    list_marker_gap_base: int = 14
    list_marker_width_base: int = 42
    unordered_marker_size_base: int = 10
    unordered_marker_shape: str = "dot"
    ordered_marker_color: str = ""
    quote_style: str = "card"
    card_radius_base: int = 6
    summary_radius_base: int = 10
    badge_radius_base: int = 5
    inline_code_radius_base: int = 6
    inline_code_pad_x_base: int = 8
    inline_code_pad_y_base: int = 5
    summary_pad_x_base: int = 18
    summary_pad_top_base: int = 24
    summary_pad_bottom_base: int = 14
    summary_badge_pad_x_base: int = 8
    summary_badge_pad_y_base: int = 4
    summary_badge_gap_base: int = 12
    code_pad_x_base: int = 18
    code_pad_top_base: int = 20
    code_pad_bottom_base: int = 13
    code_header_height_base: int = 34
    code_gutter_pad_base: int = 12
    code_gutter_gap_base: int = 14
    table_cell_pad_x_base: int = 12
    table_cell_pad_y_base: int = 10
    summary_badge_offset_x_base: int = 0
    summary_badge_offset_y_base: int = 0
    card_shadow_alpha: int = 0
    card_shadow_blur_base: int = 0
    card_shadow_offset_y_base: int = 0


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
        heading_accent="#c46b2d",
        heading_foreground="#1f2933",
        summary_background="#fbf6ee",
        summary_border="#e5dbc9",
        summary_badge_background="#c46b2d",
        summary_badge_foreground="#ffffff",
        default_width=1600,
        minimum_width=720,
        default_padding=56,
        default_scale=1.15,
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
        heading_accent="#0969da",
        heading_foreground="#1f2328",
        summary_background="#f6f8fa",
        summary_border="#d0d7de",
        summary_badge_background="#0969da",
        summary_badge_foreground="#ffffff",
        default_width=1600,
        minimum_width=720,
        default_padding=56,
        default_scale=1.15,
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
        heading_accent="#2f81f7",
        heading_foreground="#e6edf3",
        summary_background="#161b22",
        summary_border="#30363d",
        summary_badge_background="#2f81f7",
        summary_badge_foreground="#ffffff",
        default_width=1600,
        minimum_width=720,
        default_padding=56,
        default_scale=1.15,
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
        heading_accent="#cb4b16",
        heading_foreground="#586e75",
        summary_background="#f7f1df",
        summary_border="#e4dcc7",
        summary_badge_background="#cb4b16",
        summary_badge_foreground="#ffffff",
        default_width=1600,
        minimum_width=720,
        default_padding=56,
        default_scale=1.15,
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
        heading_accent="#f97316",
        heading_foreground="#e5e7eb",
        summary_background="#141b23",
        summary_border="#2c3948",
        summary_badge_background="#f97316",
        summary_badge_foreground="#0b1117",
        default_width=1600,
        minimum_width=720,
        default_padding=56,
        default_scale=1.15,
    ),
    "mobile-summary": RenderTheme(
        name="Mobile Summary",
        background="#f2f2f2",
        foreground="#1f1f1f",
        muted="#6e6e6e",
        accent="#ef4e43",
        subtle="#f2f2f2",
        border="#e8e8e8",
        quote_background="#f2f2f2",
        quote_border="#ef4e43",
        code_background="#ffffff",
        code_border="#efefef",
        table_header_background="#ffffff",
        table_row_background="#ffffff",
        table_alt_background="#f8fafc",
        link="#d94841",
        inline_code_foreground="#d47445",
        inline_code_background="#f2f2f2",
        code_style="xcode",
        heading_accent="#1f1f1f",
        heading_foreground="#1f1f1f",
        summary_background="#ffffff",
        summary_border="#efefef",
        summary_badge_background="#ef4e43",
        summary_badge_foreground="#ffffff",
        default_width=840,
        minimum_width=440,
        default_padding=54,
        default_scale=1.0,
        body_font_base=19,
        code_font_base=16,
        quote_font_base=19,
        title_font_base=18,
        heading_font_bases=(34, 21, 19, 18, 16, 15),
        heading_width_factors=(0.67, 1.0, 1.0, 1.0, 1.0, 1.0),
        body_line_gap_base=3,
        heading_line_gap_base=2,
        code_line_gap_base=2,
        heading_spacing_base=16,
        paragraph_spacing_base=9,
        quote_spacing_base=12,
        list_spacing_base=1,
        code_spacing_base=16,
        summary_spacing_base=16,
        table_spacing_base=12,
        image_spacing_base=14,
        list_inset_base=0,
        list_marker_gap_base=6,
        list_marker_width_base=20,
        unordered_marker_size_base=7,
        unordered_marker_shape="square",
        ordered_marker_color="#1f1f1f",
        quote_style="line",
        card_radius_base=0,
        summary_radius_base=0,
        badge_radius_base=0,
        inline_code_radius_base=0,
        inline_code_pad_x_base=4,
        inline_code_pad_y_base=2,
        summary_pad_x_base=18,
        summary_pad_top_base=16,
        summary_pad_bottom_base=10,
        summary_badge_pad_x_base=6,
        summary_badge_pad_y_base=3,
        summary_badge_gap_base=6,
        code_pad_x_base=14,
        code_pad_top_base=14,
        code_pad_bottom_base=10,
        code_header_height_base=30,
        code_gutter_pad_base=10,
        code_gutter_gap_base=10,
        table_cell_pad_x_base=10,
        table_cell_pad_y_base=8,
        summary_badge_offset_x_base=-8,
        summary_badge_offset_y_base=-8,
        card_shadow_alpha=8,
        card_shadow_blur_base=5,
        card_shadow_offset_y_base=1,
    ),
}

_THEME_ALIASES = {
    "阅读器": "paper",
    "reader": "paper",
    "github": "github-light",
    "github-day": "github-light",
    "github-white": "github-light",
    "solarized": "solarized-light",
    "summary-mobile": "mobile-summary",
    "手机摘要": "mobile-summary",
    "mobile": "mobile-summary",
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
    return replace(
        base,
        accent=accent,
        quote_border=accent,
        link=accent,
        heading_accent=accent if base.heading_accent == base.accent else base.heading_accent,
        summary_badge_background=accent,
    )


def list_themes() -> list[str]:
    return list(_THEMES)
