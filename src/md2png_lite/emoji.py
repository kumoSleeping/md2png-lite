from __future__ import annotations

import contextlib
import io
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx
from PIL import Image

try:
    from platformdirs import user_cache_dir
except Exception:  # pragma: no cover - optional dependency
    user_cache_dir = None  # type: ignore[assignment]

_EMOJI_CACHE_DIR_ENV = "MD2PNG_LITE_EMOJI_CACHE_DIR"
_EMOJI_SOURCE_ENV = "MD2PNG_LITE_EMOJI_SOURCE"
_TWEMOJI_TAG = "v17.0.2"
_TWEMOJI_ASSET_ROOT = f"https://raw.githubusercontent.com/jdecked/twemoji/{_TWEMOJI_TAG}/assets/72x72"
_TWEMOJI_CACHE_VERSION = f"twemoji-{_TWEMOJI_TAG}-72x72"
_ZWJ = "\u200d"
_VS15 = "\ufe0e"
_VS16 = "\ufe0f"
_KEYCAP = "\u20e3"
_CANCEL_TAG = "\U000E007F"
_EXPLICIT_EMOJI_BASES = frozenset(
    {
        0x00A9,
        0x00AE,
        0x203C,
        0x2049,
        0x2122,
        0x2139,
        0x2194,
        0x2195,
        0x2196,
        0x2197,
        0x2198,
        0x2199,
        0x21A9,
        0x21AA,
        0x231A,
        0x231B,
        0x2328,
        0x23CF,
        0x23E9,
        0x23EA,
        0x23EB,
        0x23EC,
        0x23ED,
        0x23EE,
        0x23EF,
        0x23F0,
        0x23F1,
        0x23F2,
        0x23F3,
        0x24C2,
        0x25AA,
        0x25AB,
        0x25B6,
        0x25C0,
        0x25FB,
        0x25FC,
        0x25FD,
        0x25FE,
        0x2600,
        0x2601,
        0x2602,
        0x2603,
        0x2604,
        0x260E,
        0x2611,
        0x2614,
        0x2615,
        0x2618,
        0x261D,
        0x2620,
        0x2622,
        0x2623,
        0x2626,
        0x262A,
        0x262E,
        0x262F,
        0x2638,
        0x2639,
        0x263A,
        0x2640,
        0x2642,
        0x2648,
        0x2649,
        0x264A,
        0x264B,
        0x264C,
        0x264D,
        0x264E,
        0x264F,
        0x2650,
        0x2651,
        0x2652,
        0x2653,
        0x265F,
        0x2660,
        0x2663,
        0x2665,
        0x2666,
        0x2668,
        0x267B,
        0x267E,
        0x267F,
        0x2692,
        0x2693,
        0x2694,
        0x2695,
        0x2696,
        0x2697,
        0x2699,
        0x269B,
        0x269C,
        0x26A0,
        0x26A1,
        0x26A7,
        0x26AA,
        0x26AB,
        0x26B0,
        0x26B1,
        0x26BD,
        0x26BE,
        0x26C4,
        0x26C5,
        0x26C8,
        0x26CE,
        0x26CF,
        0x26D1,
        0x26D3,
        0x26D4,
        0x26E9,
        0x26EA,
        0x26F0,
        0x26F1,
        0x26F2,
        0x26F3,
        0x26F4,
        0x26F5,
        0x26F7,
        0x26F8,
        0x26F9,
        0x26FA,
        0x26FD,
        0x2702,
        0x2705,
        0x2708,
        0x2709,
        0x270A,
        0x270B,
        0x270C,
        0x270D,
        0x270F,
        0x2712,
        0x2714,
        0x2716,
        0x271D,
        0x2721,
        0x2728,
        0x2733,
        0x2734,
        0x2744,
        0x2747,
        0x274C,
        0x274E,
        0x2753,
        0x2754,
        0x2755,
        0x2757,
        0x2763,
        0x2764,
        0x27A1,
        0x27B0,
        0x27BF,
        0x2934,
        0x2935,
        0x2B05,
        0x2B06,
        0x2B07,
        0x2B1B,
        0x2B1C,
        0x2B50,
        0x2B55,
        0x3030,
        0x303D,
        0x3297,
        0x3299,
    }
)


@dataclass(frozen=True)
class TextSegment:
    kind: str
    text: str


class EmojiAssetLoader:
    def __init__(self, *, source: str | None = None, cache_dir: str | None = None) -> None:
        self._source = _normalize_source(source or os.environ.get(_EMOJI_SOURCE_ENV))
        self._cache_root = _resolve_cache_root(cache_dir)
        self._sequence_cache: dict[str, Image.Image | None] = {}
        self._asset_cache: dict[str, Image.Image | None] = {}

    def image_for_sequence(self, sequence: str) -> Image.Image | None:
        text = str(sequence or "")
        if not text or self._source == "off":
            return None
        if text in self._sequence_cache:
            return self._sequence_cache[text]

        image: Image.Image | None = None
        for asset_name in emoji_asset_candidates(text):
            image = self._image_for_asset(asset_name)
            if image is not None:
                break
        self._sequence_cache[text] = image
        return image

    def _image_for_asset(self, asset_name: str) -> Image.Image | None:
        if not asset_name:
            return None
        if asset_name in self._asset_cache:
            return self._asset_cache[asset_name]

        png_path = self._cache_root / f"{asset_name}.png"
        missing_path = self._cache_root / f"{asset_name}.missing"
        image: Image.Image | None = None
        if png_path.is_file():
            image = _load_rgba_image(png_path)
        elif not missing_path.exists():
            image = self._download_asset(asset_name, png_path, missing_path)
        self._asset_cache[asset_name] = image
        return image

    def _download_asset(self, asset_name: str, png_path: Path, missing_path: Path) -> Image.Image | None:
        self._cache_root.mkdir(parents=True, exist_ok=True)
        url = f"{_TWEMOJI_ASSET_ROOT}/{asset_name}.png"
        try:
            response = httpx.get(url, timeout=15.0, follow_redirects=True)
        except Exception:
            return None
        if response.status_code == 404:
            with contextlib.suppress(Exception):
                missing_path.write_text("", encoding="utf-8")
            return None
        try:
            response.raise_for_status()
            image = Image.open(io.BytesIO(response.content)).convert("RGBA")
        except Exception:
            return None
        tmp_path = png_path.with_suffix(".tmp")
        try:
            tmp_path.write_bytes(response.content)
            tmp_path.replace(png_path)
        except Exception:
            with contextlib.suppress(Exception):
                tmp_path.unlink()
        with contextlib.suppress(Exception):
            missing_path.unlink()
        return image


def split_text_and_emoji(text: str) -> list[TextSegment]:
    source = str(text or "")
    if not source:
        return []
    parts: list[TextSegment] = []
    buffer: list[str] = []
    index = 0
    while index < len(source):
        size = _consume_emoji_sequence(source, index)
        if size > 0:
            if buffer:
                parts.append(TextSegment(kind="text", text="".join(buffer)))
                buffer = []
            parts.append(TextSegment(kind="emoji", text=source[index : index + size]))
            index += size
            continue
        buffer.append(source[index])
        index += 1
    if buffer:
        parts.append(TextSegment(kind="text", text="".join(buffer)))
    return parts


def emoji_asset_candidates(sequence: str) -> tuple[str, ...]:
    codepoints = [ord(ch) for ch in str(sequence or "") if ord(ch) != ord(_VS15)]
    if not codepoints:
        return ()
    exact = _asset_name_from_codepoints(codepoints)
    compact = _asset_name_from_codepoints(cp for cp in codepoints if cp != ord(_VS16))
    return tuple(dict.fromkeys(part for part in (exact, compact) if part))


def _consume_emoji_sequence(text: str, start: int) -> int:
    if start >= len(text):
        return 0
    ch = text[start]
    if _is_keycap_base(ch):
        cursor = start + 1
        if cursor < len(text) and text[cursor] == _VS16:
            cursor += 1
        if cursor < len(text) and text[cursor] == _KEYCAP:
            return cursor + 1 - start
        return 0
    if _is_regional_indicator(ch):
        if start + 1 < len(text) and _is_regional_indicator(text[start + 1]):
            return 2
        return 0

    cursor = _consume_emoji_component(text, start, allow_text_presentation=False)
    if cursor <= 0:
        return 0
    while cursor < len(text) and text[cursor] == _ZWJ:
        next_cursor = _consume_emoji_component(text, cursor + 1, allow_text_presentation=True)
        if next_cursor <= cursor + 1:
            break
        cursor = next_cursor
    return cursor - start


def _consume_emoji_component(text: str, start: int, *, allow_text_presentation: bool) -> int:
    if start >= len(text):
        return 0
    ch = text[start]
    if not _is_emoji_component_base(ch, allow_text_presentation=allow_text_presentation):
        return 0

    cursor = start + 1
    saw_vs16 = False
    while cursor < len(text) and text[cursor] in {_VS15, _VS16}:
        if text[cursor] == _VS15 and not allow_text_presentation:
            return 0
        saw_vs16 = saw_vs16 or text[cursor] == _VS16
        cursor += 1

    if _requires_emoji_presentation(ch) and not saw_vs16 and not allow_text_presentation:
        return 0

    if cursor < len(text) and _is_emoji_modifier(text[cursor]):
        cursor += 1
    if cursor < len(text) and _is_tag_spec(text[cursor]):
        tag_cursor = cursor
        while tag_cursor < len(text) and _is_tag_spec(text[tag_cursor]):
            tag_cursor += 1
        if tag_cursor < len(text) and text[tag_cursor] == _CANCEL_TAG:
            cursor = tag_cursor + 1
    return cursor


def _is_emoji_component_base(ch: str, *, allow_text_presentation: bool) -> bool:
    code = ord(ch)
    if code >= 0x1F000:
        return True
    if code in _EXPLICIT_EMOJI_BASES:
        return True
    if allow_text_presentation and code in {0x2640, 0x2642, 0x2695, 0x2764}:
        return True
    return False


def _requires_emoji_presentation(ch: str) -> bool:
    return ord(ch) < 0x1F000


def _is_emoji_modifier(ch: str) -> bool:
    code = ord(ch)
    return 0x1F3FB <= code <= 0x1F3FF


def _is_keycap_base(ch: str) -> bool:
    return ch in "#*0123456789"


def _is_regional_indicator(ch: str) -> bool:
    code = ord(ch)
    return 0x1F1E6 <= code <= 0x1F1FF


def _is_tag_spec(ch: str) -> bool:
    code = ord(ch)
    return 0xE0020 <= code <= 0xE007E


def _asset_name_from_codepoints(codepoints: object) -> str:
    return "-".join(f"{int(codepoint):x}" for codepoint in codepoints)


def _normalize_source(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"off", "none", "false", "0"}:
        return "off"
    return "twemoji"


def _resolve_cache_root(raw: str | None) -> Path:
    env_value = str(raw or os.environ.get(_EMOJI_CACHE_DIR_ENV) or "").strip()
    if env_value:
        return Path(env_value).expanduser()
    if callable(user_cache_dir):
        return Path(str(user_cache_dir("md2png-lite"))) / "emoji" / _TWEMOJI_CACHE_VERSION
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "md2png-lite" / "emoji" / _TWEMOJI_CACHE_VERSION
    if sys.platform == "win32":
        local_appdata = str(os.environ.get("LOCALAPPDATA") or "").strip()
        if local_appdata:
            return Path(local_appdata) / "md2png-lite" / "emoji" / _TWEMOJI_CACHE_VERSION
    return Path.home() / ".cache" / "md2png-lite" / "emoji" / _TWEMOJI_CACHE_VERSION


def _load_rgba_image(path: Path) -> Image.Image | None:
    try:
        with Image.open(path) as image:
            return image.convert("RGBA")
    except Exception:
        return None
