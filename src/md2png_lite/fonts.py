from __future__ import annotations

import contextlib
import locale
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from PIL import ImageFont

from .font_sync import resolved_font_pack, synced_font_dirs

try:
    from fontTools.ttLib import TTCollection, TTFont
except Exception:  # pragma: no cover - dependency should exist with matplotlib
    TTCollection = None  # type: ignore[assignment]
    TTFont = None  # type: ignore[assignment]

try:
    from matplotlib.font_manager import findSystemFonts
    from matplotlib.ft2font import FT2Font
except Exception:  # pragma: no cover - dependency should exist in normal env
    findSystemFonts = None  # type: ignore[assignment]
    FT2Font = None  # type: ignore[assignment]

_FONT_EXTENSIONS = {".ttf", ".ttc", ".otf", ".otc"}
_COLLECTION_EXTENSIONS = {".ttc", ".otc"}
_CJK_RANGES = (
    ("\u3400", "\u9fff"),
    ("\uf900", "\ufaff"),
    ("\u3040", "\u30ff"),
    ("\u31f0", "\u31ff"),
    ("\uac00", "\ud7af"),
)

_SYSTEM_FONT_DIRS = {
    "darwin": (
        "/System/Library/Fonts",
        "/System/Library/Fonts/Supplemental",
        "/System/Library/PrivateFrameworks/FontServices.framework/Resources/Reserved",
        "/Library/Fonts",
        "~/Library/Fonts",
    ),
    "win32": (
        "C:/Windows/Fonts",
        "~/AppData/Local/Microsoft/Windows/Fonts",
    ),
    "linux": (
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        "~/.fonts",
        "~/.local/share/fonts",
    ),
}

_PLATFORM_ROLE_PREFERENCES = {
    "darwin": {
        "sans": (
            "SF Pro Text",
            ".SF NS Text",
            "Helvetica Neue",
            "Helvetica",
            "Avenir Next",
            "Avenir",
            "Arial",
            "DejaVu Sans",
            "Liberation Sans",
        ),
        "mono": (
            "SF Mono",
            "SFNSMono",
            "Menlo",
            "Monaco",
            "JetBrains Mono",
            "Cascadia Mono",
            "DejaVu Sans Mono",
            "Liberation Mono",
        ),
        "cjk_zh_hans": (
            "Noto Sans SC",
            "PingFang SC",
            ".PingFang UI SC",
            ".PingFang UI Text SC",
            "Noto Sans CJK SC",
            "Source Han Sans SC",
            "Hiragino Sans GB",
            "STHeiti",
            "Heiti SC",
            "Microsoft YaHei",
            "SimHei",
            "Arial Unicode",
            "DejaVu Sans",
        ),
        "cjk_zh_hant": (
            "PingFang TC",
            ".PingFang UI TC",
            ".PingFang UI Text TC",
            "Heiti TC",
            "Songti TC",
            "Noto Sans CJK TC",
            "Noto Sans TC",
            "Source Han Sans TC",
            "Microsoft JhengHei",
            "Arial Unicode",
            "DejaVu Sans",
        ),
        "cjk_ja": (
            "Hiragino Sans",
            "Hiragino Kaku Gothic",
            "Yu Gothic",
            "Meiryo",
            "Noto Sans CJK JP",
            "Noto Sans JP",
            "Source Han Sans JP",
            "Arial Unicode",
            "DejaVu Sans",
        ),
        "cjk_ko": (
            "Apple SD Gothic Neo",
            "Malgun Gothic",
            "Noto Sans CJK KR",
            "Noto Sans KR",
            "Source Han Sans K",
            "Arial Unicode",
            "DejaVu Sans",
        ),
    },
    "win32": {
        "sans": (
            "Noto Sans",
            "Segoe UI",
            "Arial",
            "DejaVu Sans",
            "Liberation Sans",
        ),
        "mono": (
            "Cascadia Mono",
            "Consolas",
            "JetBrains Mono",
            "DejaVu Sans Mono",
            "Liberation Mono",
        ),
        "cjk_zh_hans": (
            "Noto Sans SC",
            "Noto Sans CJK SC",
            "Source Han Sans SC",
            "Microsoft YaHei UI",
            "Microsoft YaHei",
            "SimHei",
            "SimSun",
            "Arial Unicode",
            "DejaVu Sans",
        ),
        "cjk_zh_hant": (
            "Microsoft JhengHei UI",
            "Microsoft JhengHei",
            "Noto Sans CJK TC",
            "Noto Sans TC",
            "Source Han Sans TC",
            "Arial Unicode",
            "DejaVu Sans",
        ),
        "cjk_ja": (
            "Yu Gothic UI",
            "Yu Gothic",
            "Meiryo",
            "Noto Sans CJK JP",
            "Noto Sans JP",
            "Source Han Sans JP",
            "Arial Unicode",
            "DejaVu Sans",
        ),
        "cjk_ko": (
            "Malgun Gothic",
            "Noto Sans CJK KR",
            "Noto Sans KR",
            "Source Han Sans K",
            "Arial Unicode",
            "DejaVu Sans",
        ),
    },
    "linux": {
        "sans": (
            "Noto Sans",
            "Ubuntu Sans",
            "Cantarell",
            "DejaVu Sans",
            "Liberation Sans",
            "Arial",
        ),
        "mono": (
            "JetBrains Mono",
            "Cascadia Mono",
            "DejaVu Sans Mono",
            "Liberation Mono",
        ),
        "cjk_zh_hans": (
            "Noto Sans SC",
            "Noto Sans CJK SC",
            "Source Han Sans SC",
            "WenQuanYi Zen Hei",
            "Microsoft YaHei",
            "SimHei",
            "Arial Unicode",
            "DejaVu Sans",
        ),
        "cjk_zh_hant": (
            "Noto Sans CJK TC",
            "Noto Sans TC",
            "Noto Sans TC",
            "Source Han Sans TC",
            "Arial Unicode",
            "DejaVu Sans",
        ),
        "cjk_ja": (
            "Noto Sans CJK JP",
            "Noto Sans JP",
            "Source Han Sans JP",
            "Meiryo",
            "Yu Gothic",
            "Arial Unicode",
            "DejaVu Sans",
        ),
        "cjk_ko": (
            "Noto Sans CJK KR",
            "Noto Sans KR",
            "Source Han Sans K",
            "Malgun Gothic",
            "Arial Unicode",
            "DejaVu Sans",
        ),
    },
}

_UNICODE_FALLBACK_KEYWORDS = (
    "noto",
    "source han",
    "arial unicode",
    "dejavu",
    "liberation",
    "segoe",
    "pingfang",
    "hiragino",
    "yahei",
    "jhenghei",
    "meiryo",
    "gothic",
    "wenquanyi",
)

_SIMPLIFIED_HINTS = frozenset("这还吗后发体样为国门页里复与关显点应实么简台湾广东数据")
_TRADITIONAL_HINTS = frozenset("這還嗎後發體樣為國門頁裡複與關顯點應實麼簡臺灣廣東數據")
_NO_LINE_START_PUNCTUATION = frozenset("，。、；：！？）》】」』’”％%!?;:,.)]}>")


@dataclass(frozen=True)
class FontEntry:
    path: str
    family: str
    style: str
    custom: bool = False
    index: int = 0
    postscript_name: str = ""

    @property
    def full_name(self) -> str:
        parts = [self.family.strip(), self.style.strip()]
        return " ".join(part for part in parts if part).strip()

    @property
    def cache_key(self) -> tuple[str, int]:
        return (self.path, int(self.index))


def _system_font_dirs() -> tuple[str, ...]:
    return _SYSTEM_FONT_DIRS.get(sys.platform, _SYSTEM_FONT_DIRS["linux"])


def _split_env_list(name: str) -> list[str]:
    value = str(os.environ.get(name) or "").strip()
    if not value:
        return []
    return [part for part in value.split(os.pathsep) if str(part or "").strip()]


def _normalize_paths(values: Iterable[str | Path]) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for value in values:
        path = Path(str(value or "")).expanduser()
        key = str(path)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


@lru_cache(maxsize=1)
def _discover_system_font_entries() -> tuple[FontEntry, ...]:
    entries: list[FontEntry] = []
    font_paths: list[str] = []
    if callable(findSystemFonts):
        dirs = [str(Path(p).expanduser()) for p in _system_font_dirs() if Path(p).expanduser().exists()]
        font_paths.extend(findSystemFonts(fontpaths=dirs, fontext="ttf"))
        font_paths.extend(findSystemFonts(fontpaths=dirs, fontext="otf"))
    for root in _normalize_paths(_system_font_dirs()):
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() in _FONT_EXTENSIONS:
                font_paths.append(str(path))

    seen: set[str] = set()
    for raw in font_paths:
        path = Path(str(raw)).expanduser()
        if not path.is_file():
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        entries.extend(_build_font_entries(path, custom=False))
    return tuple(entries)


def _build_font_entries(path: Path, *, custom: bool) -> list[FontEntry]:
    ext = path.suffix.lower()
    if TTCollection is not None and ext in _COLLECTION_EXTENSIONS:
        with contextlib.suppress(Exception):
            collection = TTCollection(str(path), lazy=True)
            try:
                entries = [
                    entry
                    for index, font in enumerate(collection.fonts)
                    if (entry := _build_font_entry_from_ttfont(path, font, custom=custom, index=index)) is not None
                ]
            finally:
                with contextlib.suppress(Exception):
                    collection.close()
            if entries:
                return entries
    if TTFont is not None:
        with contextlib.suppress(Exception):
            font = TTFont(str(path), lazy=True)
            try:
                entry = _build_font_entry_from_ttfont(path, font, custom=custom, index=0)
            finally:
                with contextlib.suppress(Exception):
                    font.close()
            if entry is not None:
                return [entry]
    legacy = _build_font_entry_legacy(path, custom=custom)
    return [legacy] if legacy is not None else []


def _build_font_entry_from_ttfont(path: Path, font: TTFont, *, custom: bool, index: int) -> FontEntry | None:
    if not _font_loadable(str(path), int(index)):
        return None
    family = _tt_name(font, 16, 1) or path.stem
    style = _tt_name(font, 17, 2)
    postscript_name = _tt_name(font, 6, 4)
    return FontEntry(
        path=str(path),
        family=family.strip() or path.stem,
        style=style.strip(),
        custom=custom,
        index=int(index),
        postscript_name=postscript_name.strip(),
    )


def _build_font_entry_legacy(path: Path, *, custom: bool) -> FontEntry | None:
    if FT2Font is None or not _font_loadable(str(path), 0):
        return None
    try:
        face = FT2Font(str(path))
    except Exception:
        return None
    family = str(getattr(face, "family_name", "") or path.stem).strip() or path.stem
    style = str(getattr(face, "style_name", "") or "").strip()
    return FontEntry(path=str(path), family=family, style=style, custom=custom, index=0)


def _tt_name(font: TTFont, *name_ids: int) -> str:
    names = getattr(font, "reader", None)
    if "name" not in font:
        return ""
    table = font["name"]
    for name_id in name_ids:
        with contextlib.suppress(Exception):
            value = table.getDebugName(name_id)
            if value:
                return str(value).strip()
    return ""


class FontRegistry:
    def __init__(
        self,
        *,
        font_paths: list[str] | None = None,
        font_dirs: list[str] | None = None,
        font_pack: str | None = None,
    ) -> None:
        self._font_pack = resolved_font_pack(font_pack)
        self._custom_entries = self._load_custom_entries(font_paths=font_paths, font_dirs=font_dirs, font_pack=font_pack)
        self._system_entries = list(_discover_system_font_entries())
        self._selection_cache: dict[tuple[str, tuple[str, ...], bool, bool], tuple[str, int]] = {}

    def _load_custom_entries(
        self,
        *,
        font_paths: list[str] | None,
        font_dirs: list[str] | None,
        font_pack: str | None,
    ) -> list[FontEntry]:
        raw_paths: list[str] = []
        raw_dirs: list[str] = []
        raw_paths.extend(_split_env_list("MD2PNG_LITE_FONT_PATHS"))
        raw_dirs.extend(_split_env_list("MD2PNG_LITE_FONT_DIRS"))
        raw_paths.extend(str(item) for item in (font_paths or []))
        raw_dirs.extend(str(path) for path in synced_font_dirs(font_pack))
        raw_dirs.extend(str(item) for item in (font_dirs or []))

        candidates: list[Path] = []
        for path in _normalize_paths(raw_paths):
            if path.is_file() and path.suffix.lower() in _FONT_EXTENSIONS:
                candidates.append(path)
        for root in _normalize_paths(raw_dirs):
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if path.suffix.lower() in _FONT_EXTENSIONS:
                    candidates.append(path)

        entries: list[FontEntry] = []
        seen: set[str] = set()
        for path in candidates:
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            entries.extend(_build_font_entries(path, custom=True))
        return entries

    def font_for_text(
        self,
        text: str,
        *,
        size: int,
        role: str = "sans",
        bold: bool = False,
        italic: bool = False,
    ) -> ImageFont.ImageFont:
        normalized = str(text or "")
        preferred_role = _resolved_role(normalized, role)
        entry = self._best_entry(normalized, preferred_role, bold=bold, italic=italic)
        if entry is None and preferred_role != "sans":
            entry = self._best_entry(normalized, "sans", bold=bold, italic=italic)
        if entry is None:
            entry = self._fallback_entry(preferred_role)
        if entry is None:
            return ImageFont.load_default()
        return _load_font_object(entry.path, size, entry.index)

    def primary_entry(
        self,
        text: str,
        *,
        role: str = "sans",
        bold: bool = False,
        italic: bool = False,
    ) -> FontEntry | None:
        normalized = str(text or "")
        preferred_role = _resolved_role(normalized, role)
        entry = self._best_entry(normalized, preferred_role, bold=bold, italic=italic)
        if entry is None:
            entry = self._fallback_entry(preferred_role)
        return entry

    def text_covered_by_entry(self, entry: FontEntry | None, text: str) -> bool:
        if entry is None:
            return False
        chars = _meaningful_chars(text)
        if not chars:
            return True
        return _glyph_coverage(entry.path, entry.index, chars) >= len(chars)

    def font_from_entry(self, entry: FontEntry | None, size: int) -> ImageFont.ImageFont:
        if entry is None:
            return ImageFont.load_default()
        return _load_font_object(entry.path, size, entry.index)

    def _best_entry(self, text: str, role: str, *, bold: bool, italic: bool) -> FontEntry | None:
        chars = _meaningful_chars(text)
        resolved_role = _resolved_role(text, role)
        cache_key = (resolved_role, chars, bool(bold), bool(italic))
        cached = self._selection_cache.get(cache_key)
        if cached:
            for entry in self._custom_entries + self._system_entries:
                if entry.cache_key == cached:
                    return entry
        buckets = self._entries_for_role(resolved_role, text=text, bold=bold, italic=italic)
        best: tuple[int, int, FontEntry] | None = None
        for order, entry in enumerate(buckets):
            score = _glyph_coverage(entry.path, entry.index, chars)
            if score <= 0:
                continue
            if best is None or score > best[0] or (score == best[0] and order < best[1]):
                best = (score, order, entry)
            if chars and score >= len(chars):
                self._selection_cache[cache_key] = entry.cache_key
                return entry
        if best is not None:
            self._selection_cache[cache_key] = best[2].cache_key
            return best[2]
        fallback = self._best_any_entry(chars, preferred_role=resolved_role)
        if fallback is not None:
            self._selection_cache[cache_key] = fallback.cache_key
        return fallback

    def _fallback_entry(self, role: str) -> FontEntry | None:
        buckets = self._entries_for_role(role, text="", bold=False, italic=False)
        if buckets:
            return buckets[0]
        return self._custom_entries[0] if self._custom_entries else (self._system_entries[0] if self._system_entries else None)

    def _entries_for_role(self, role: str, *, text: str, bold: bool, italic: bool) -> list[FontEntry]:
        resolved_role = _resolved_role(text, role)
        preferences = _role_preferences_for_text(text, resolved_role, prefer_noto=self._font_pack == "noto")
        entries = self._custom_entries + self._system_entries
        ranked: list[tuple[int, FontEntry]] = []
        for entry in entries:
            family_score = _family_rank(entry, preferences)
            style_bonus = _style_rank(entry, bold=bold, italic=italic)
            penalty = _entry_penalty(entry, resolved_role)
            if family_score < len(preferences) + 8 or entry.custom:
                ranked.append((family_score * 10 + style_bonus + penalty, entry))
        ranked.sort(key=lambda item: item[0])
        seen: set[tuple[str, int]] = set()
        ordered: list[FontEntry] = []
        for _, entry in ranked:
            key = entry.cache_key
            if key in seen:
                continue
            seen.add(key)
            ordered.append(entry)
        if ordered:
            return ordered
        return [entry for entry in entries if entry.custom][:8] + self._unicode_fallback_entries(preferred_role=resolved_role)

    def _best_any_entry(self, chars: tuple[str, ...], *, preferred_role: str) -> FontEntry | None:
        if not chars:
            return None
        candidates = self._unicode_fallback_entries(preferred_role=preferred_role)
        if not candidates:
            candidates = self._custom_entries + self._system_entries[:64]
        best: tuple[int, int, FontEntry] | None = None
        for order, entry in enumerate(candidates):
            score = _glyph_coverage(entry.path, entry.index, chars)
            if score <= 0:
                continue
            if best is None or score > best[0] or (score == best[0] and order < best[1]):
                best = (score, order, entry)
            if score >= len(chars):
                return entry
        return best[2] if best is not None else None

    def _unicode_fallback_entries(self, *, preferred_role: str) -> list[FontEntry]:
        entries = self._custom_entries + self._system_entries
        ranked: list[tuple[int, FontEntry]] = []
        for entry in entries:
            hay = _entry_haystack(entry)
            if entry.custom:
                ranked.append((0, entry))
                continue
            for index, keyword in enumerate(_UNICODE_FALLBACK_KEYWORDS):
                if keyword in hay:
                    ranked.append((index + 1 + _entry_penalty(entry, preferred_role), entry))
                    break
        ranked.sort(key=lambda item: item[0])
        seen: set[tuple[str, int]] = set()
        ordered: list[FontEntry] = []
        for _, entry in ranked:
            if entry.cache_key in seen:
                continue
            seen.add(entry.cache_key)
            ordered.append(entry)
        return ordered[:48]


def _role_preferences_for_text(text: str, role: str, *, prefer_noto: bool = False) -> tuple[str, ...]:
    resolved_role = _resolved_role(text, role)
    platform_roles = _PLATFORM_ROLE_PREFERENCES.get(sys.platform, _PLATFORM_ROLE_PREFERENCES["linux"])
    if prefer_noto:
        noto_preferences = _noto_role_preferences(resolved_role)
        base_preferences = platform_roles.get(resolved_role, platform_roles.get("sans", ()))
        return tuple(dict.fromkeys((*noto_preferences, *base_preferences)))
    if resolved_role in platform_roles:
        return platform_roles[resolved_role]
    if resolved_role.startswith("cjk_"):
        return platform_roles.get("cjk_zh_hans", ())
    return platform_roles.get("sans", ())


def _noto_role_preferences(role: str) -> tuple[str, ...]:
    return {
        "sans": ("Noto Sans",),
        "cjk_zh_hans": ("Noto Sans CJK SC", "Noto Sans SC"),
        "cjk_zh_hant": ("Noto Sans CJK TC", "Noto Sans TC"),
        "cjk_ja": ("Noto Sans CJK JP", "Noto Sans JP", "Noto Sans SC"),
        "cjk_ko": ("Noto Sans CJK KR", "Noto Sans KR"),
    }.get(role, ())


def _resolved_role(text: str, role: str) -> str:
    base_role = str(role or "sans").strip() or "sans"
    if base_role == "mono":
        return "mono"
    if base_role.startswith("cjk_"):
        return base_role
    normalized = str(text or "")
    if any(_is_cjk(ch) for ch in normalized) or base_role == "cjk":
        return _dominant_cjk_role(normalized)
    return "sans"


def _dominant_cjk_role(text: str) -> str:
    han = 0
    kana = 0
    hangul = 0
    for ch in str(text or ""):
        if _is_hangul(ch):
            hangul += 1
        elif _is_kana(ch):
            kana += 1
        elif _is_han(ch):
            han += 1
    if hangul:
        return "cjk_ko"
    if kana:
        return "cjk_ja"
    if han:
        return "cjk_zh_hant" if _preferred_han_variant(text) == "zh_hant" else "cjk_zh_hans"
    tag = _system_locale_tag()
    if tag.startswith("ja"):
        return "cjk_ja"
    if tag.startswith("ko"):
        return "cjk_ko"
    if "zh_hk" in tag or "zh_tw" in tag or "hant" in tag:
        return "cjk_zh_hant"
    return "cjk_zh_hans"


def _preferred_han_variant(text: str) -> str:
    trad = sum(1 for ch in str(text or "") if ch in _TRADITIONAL_HINTS)
    simp = sum(1 for ch in str(text or "") if ch in _SIMPLIFIED_HINTS)
    if trad > simp:
        return "zh_hant"
    if simp > trad:
        return "zh_hans"
    tag = _system_locale_tag()
    if "zh_hk" in tag or "zh_tw" in tag or "hant" in tag:
        return "zh_hant"
    return "zh_hans"


@lru_cache(maxsize=1)
def _system_locale_tag() -> str:
    for name in ("LC_ALL", "LC_CTYPE", "LANG"):
        value = str(os.environ.get(name) or "").strip()
        if value:
            return value.replace("-", "_").lower()
    with contextlib.suppress(Exception):
        value = locale.getlocale()[0] or locale.getdefaultlocale()[0]  # type: ignore[attr-defined]
        if value:
            return str(value).replace("-", "_").lower()
    return ""


def _entry_haystack(entry: FontEntry) -> str:
    return f"{entry.family} {entry.full_name} {entry.postscript_name} {Path(entry.path).stem}".lower()


def _family_rank(entry: FontEntry, preferences: tuple[str, ...]) -> int:
    haystacks = (
        entry.family.lower(),
        entry.full_name.lower(),
        entry.postscript_name.lower(),
        Path(entry.path).stem.lower(),
    )
    for index, preferred in enumerate(preferences):
        needle = preferred.lower()
        if any(needle in hay for hay in haystacks):
            return index
    return len(preferences) + (0 if entry.custom else 20)


def _style_rank(entry: FontEntry, *, bold: bool, italic: bool) -> int:
    style = f"{entry.style} {entry.postscript_name}".lower()
    score = 0
    weight = _style_weight(style)
    is_boldish = any(token in style for token in ("bold", "semibold", "demi", "medium", "w6", "w7", "w8", "w9"))
    is_italicish = any(token in style for token in ("italic", "oblique"))
    if weight is not None:
        target_weight = 7 if bold else 4
        score += abs(weight - target_weight)
        if not bold and weight <= 1:
            score += 6
        if not bold and weight == 2:
            score += 3
    if bold:
        if not is_boldish:
            score += 3
    elif is_boldish:
        score += 1
    if italic:
        if not is_italicish:
            score += 3
    elif is_italicish:
        score += 4
    return score


def _style_weight(style: str) -> int | None:
    hay = str(style or "").lower()
    match = re.search(r"(?:^|[^a-z0-9])w([0-9])(?:$|[^a-z0-9])", hay)
    if match:
        return int(match.group(1))
    if any(token in hay for token in ("ultralight", "ultra light", "thin", "hairline")):
        return 1
    if any(token in hay for token in ("extralight", "extra light")):
        return 2
    if "light" in hay:
        return 3
    if any(token in hay for token in ("regular", "normal", "roman", "book")):
        return 4
    if "medium" in hay:
        return 5
    if any(token in hay for token in ("semibold", "semi bold", "demibold", "demi bold")):
        return 6
    if any(token in hay for token in ("extrabold", "extra bold", "ultrabold", "ultra bold")):
        return 8
    if any(token in hay for token in ("black", "heavy")):
        return 9
    if "bold" in hay:
        return 7
    return None


def _entry_penalty(entry: FontEntry, role: str) -> int:
    hay = _entry_haystack(entry)
    penalty = 0
    if role == "sans":
        if "mono" in hay:
            penalty += 24
        if any(token in hay for token in ("pingfang", "hiragino", "songti", "stheiti", "heiti", "gothic", "meiryo")):
            penalty += 8
        if any(
            token in hay
            for token in (
                "noto sans sc",
                "noto sans tc",
                "noto sans jp",
                "noto sans kr",
                "noto sans cjk",
                "source han",
            )
        ):
            penalty += 12
        if "arial unicode" in hay:
            penalty += 16
    elif role == "mono":
        if not any(
            token in hay
            for token in ("mono", "code", "menlo", "monaco", "sfnsmono", "consolas", "cascadia", "jetbrains")
        ):
            penalty += 12
    elif role == "cjk_zh_hans":
        if "arial unicode" in hay:
            penalty += 24
        if any(token in hay for token in ("songti", "mincho", "serif")):
            penalty += 18
        if "hiragino sans" in hay and "gb" not in hay:
            penalty += 18
        if any(token in hay for token in (" tc", "tc-", " tc.", "hant", "hk", "mo")):
            penalty += 10
    elif role == "cjk_zh_hant":
        if "arial unicode" in hay:
            penalty += 24
        if any(token in hay for token in ("songti sc", " gb", "gb.", "sc-", "simplified")):
            penalty += 10
    elif role == "cjk_ja":
        if any(token in hay for token in ("gb", "sc", "pingfang sc", "stheiti")):
            penalty += 12
        if "songti" in hay:
            penalty += 18
    elif role == "cjk_ko":
        if any(token in hay for token in ("gb", "sc", "tc", "songti", "hiragino")):
            penalty += 12
    return penalty


def _meaningful_chars(text: str) -> tuple[str, ...]:
    chars: list[str] = []
    seen: set[str] = set()
    for ch in str(text or ""):
        if ch.isspace() or ord(ch) < 32:
            continue
        if ch in seen:
            continue
        seen.add(ch)
        chars.append(ch)
    return tuple(chars)


@lru_cache(maxsize=4096)
def _glyph_coverage(path: str, index: int, chars: tuple[str, ...]) -> int:
    if not chars:
        return 1
    codepoints = _font_codepoints(path, int(index))
    if codepoints:
        return sum(1 for ch in chars if ord(ch) in codepoints)
    if FT2Font is None:
        return 0
    try:
        face = FT2Font(path)
    except Exception:
        return 0
    score = 0
    for ch in chars:
        with contextlib.suppress(Exception):
            if face.get_char_index(ord(ch)) > 0:
                score += 1
    return score


@lru_cache(maxsize=1024)
def _font_codepoints(path: str, index: int) -> frozenset[int]:
    font_path = Path(path)
    if TTCollection is not None and font_path.suffix.lower() in _COLLECTION_EXTENSIONS:
        with contextlib.suppress(Exception):
            collection = TTCollection(path, lazy=True)
            try:
                if 0 <= int(index) < len(collection.fonts):
                    return _extract_codepoints(collection.fonts[int(index)])
            finally:
                with contextlib.suppress(Exception):
                    collection.close()
    if TTFont is not None:
        with contextlib.suppress(Exception):
            font = TTFont(path, lazy=True)
            try:
                return _extract_codepoints(font)
            finally:
                with contextlib.suppress(Exception):
                    font.close()
    return frozenset()


def _extract_codepoints(font: TTFont) -> frozenset[int]:
    codepoints: set[int] = set()
    with contextlib.suppress(Exception):
        cmap = font["cmap"]
        for table in cmap.tables:
            codepoints.update(int(codepoint) for codepoint in table.cmap.keys())
    return frozenset(codepoints)


@lru_cache(maxsize=2048)
def _font_loadable(path: str, index: int) -> bool:
    try:
        ImageFont.truetype(path, size=12, index=max(0, int(index)))
        return True
    except Exception:
        return False


@lru_cache(maxsize=1024)
def _load_font_object(path: str, size: int, index: int) -> ImageFont.ImageFont:
    return ImageFont.truetype(path, size=max(12, int(size)), index=max(0, int(index)))


def _is_han(ch: str) -> bool:
    if not ch:
        return False
    code = ord(ch)
    return (0x3400 <= code <= 0x9FFF) or (0xF900 <= code <= 0xFAFF)


def _is_kana(ch: str) -> bool:
    if not ch:
        return False
    code = ord(ch)
    return (0x3040 <= code <= 0x30FF) or (0x31F0 <= code <= 0x31FF)


def _is_hangul(ch: str) -> bool:
    if not ch:
        return False
    code = ord(ch)
    return 0xAC00 <= code <= 0xD7AF


def _is_cjk(ch: str) -> bool:
    if not ch:
        return False
    if any(start <= ch <= end for start, end in _CJK_RANGES):
        return True
    return unicodedata.east_asian_width(ch) in {"W", "F"}
