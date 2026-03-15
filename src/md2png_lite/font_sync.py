from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

try:
    from filelock import FileLock
except Exception:  # pragma: no cover - optional extra
    FileLock = None  # type: ignore[assignment]

try:
    from platformdirs import user_cache_dir
except Exception:  # pragma: no cover - optional extra
    user_cache_dir = None  # type: ignore[assignment]

_FONT_PACK_ENV = "MD2PNG_LITE_FONT_PACK"
_NOTO_PACK_VERSION = "noto-sans-v1"


@dataclass(frozen=True)
class _RemoteFont:
    filename: str
    url: str
    min_bytes: int


_NOTO_FONT_MANIFEST: tuple[_RemoteFont, ...] = (
    _RemoteFont("NotoSans-Regular.ttf", "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf", 120_000),
    _RemoteFont("NotoSans-Bold.ttf", "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf", 120_000),
    _RemoteFont("NotoSans-Italic.ttf", "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSans/NotoSans-Italic.ttf", 120_000),
    _RemoteFont("NotoSans-BoldItalic.ttf", "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSans/NotoSans-BoldItalic.ttf", 120_000),
    _RemoteFont("NotoSansArabic-Regular.ttf", "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSansArabic/NotoSansArabic-Regular.ttf", 40_000),
    _RemoteFont("NotoSansArabic-Bold.ttf", "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSansArabic/NotoSansArabic-Bold.ttf", 40_000),
    _RemoteFont("NotoSansDevanagari-Regular.ttf", "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSansDevanagari/NotoSansDevanagari-Regular.ttf", 40_000),
    _RemoteFont("NotoSansDevanagari-Bold.ttf", "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSansDevanagari/NotoSansDevanagari-Bold.ttf", 40_000),
    _RemoteFont("NotoSansHebrew-Regular.ttf", "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSansHebrew/NotoSansHebrew-Regular.ttf", 10_000),
    _RemoteFont("NotoSansHebrew-Bold.ttf", "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSansHebrew/NotoSansHebrew-Bold.ttf", 10_000),
    _RemoteFont("NotoSansThai-Regular.ttf", "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSansThai/NotoSansThai-Regular.ttf", 10_000),
    _RemoteFont("NotoSansThai-Bold.ttf", "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSansThai/NotoSansThai-Bold.ttf", 10_000),
    _RemoteFont("NotoSansCJKsc-Regular.otf", "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf", 5_000_000),
    _RemoteFont("NotoSansCJKsc-Bold.otf", "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Bold.otf", 5_000_000),
    _RemoteFont("NotoSansCJKjp-Regular.otf", "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/Japanese/NotoSansCJKjp-Regular.otf", 5_000_000),
    _RemoteFont("NotoSansCJKjp-Bold.otf", "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/Japanese/NotoSansCJKjp-Bold.otf", 5_000_000),
    _RemoteFont("NotoSansCJKkr-Regular.otf", "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/Korean/NotoSansCJKkr-Regular.otf", 5_000_000),
    _RemoteFont("NotoSansCJKkr-Bold.otf", "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/Korean/NotoSansCJKkr-Bold.otf", 5_000_000),
    _RemoteFont("NotoSansCJKtc-Regular.otf", "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf", 5_000_000),
    _RemoteFont("NotoSansCJKtc-Bold.otf", "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Bold.otf", 5_000_000),
)


def normalize_font_pack(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"noto", "notosans", "noto-sans"}:
        return "noto"
    if raw in {"system", "default"}:
        return "system"
    return "auto"


def noto_sync_available() -> bool:
    return FileLock is not None and callable(user_cache_dir)


def resolved_font_pack(value: str | None = None) -> str:
    mode = normalize_font_pack(value or os.environ.get(_FONT_PACK_ENV))
    if mode == "auto":
        return "noto" if noto_sync_available() else "system"
    if mode == "noto" and not noto_sync_available():
        return "system"
    return mode


def synced_font_dirs(font_pack: str | None = None) -> list[str]:
    if resolved_font_pack(font_pack) != "noto":
        return []
    synced = ensure_noto_fonts()
    return [str(synced)] if synced is not None else []


def ensure_noto_fonts() -> Path | None:
    if not noto_sync_available() or FileLock is None or not callable(user_cache_dir):
        return None
    cache_root = Path(str(user_cache_dir("md2png-lite"))) / "fonts" / _NOTO_PACK_VERSION
    cache_root.mkdir(parents=True, exist_ok=True)
    lock_path = cache_root.parent / f"{_NOTO_PACK_VERSION}.lock"
    lock = FileLock(str(lock_path))
    try:
        with lock:
            for remote in _NOTO_FONT_MANIFEST:
                target = cache_root / remote.filename
                if target.is_file() and target.stat().st_size >= remote.min_bytes:
                    continue
                _download_font(remote, target)
    except Exception:
        valid = [remote for remote in _NOTO_FONT_MANIFEST if _font_ready(cache_root / remote.filename, remote.min_bytes)]
        return cache_root if valid else None
    return cache_root


def _download_font(remote: _RemoteFont, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    with contextlib.suppress(FileNotFoundError):
        tmp.unlink()
    try:
        with httpx.stream("GET", remote.url, follow_redirects=True, timeout=120.0) as response:
            response.raise_for_status()
            with tmp.open("wb") as handle:
                for chunk in response.iter_bytes():
                    if chunk:
                        handle.write(chunk)
        if not _font_ready(tmp, remote.min_bytes):
            raise ValueError(f"downloaded font is smaller than expected: {remote.filename}")
        tmp.replace(target)
    finally:
        if tmp.exists():
            with contextlib.suppress(Exception):
                tmp.unlink()


def _font_ready(path: Path, min_bytes: int) -> bool:
    return path.is_file() and path.stat().st_size >= int(min_bytes)
