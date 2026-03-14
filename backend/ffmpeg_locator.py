"""Helpers for discovering FFmpeg and FFprobe binaries."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .runtime_paths import bundle_root, runtime_root
from .settings import get_saved_ffmpeg_path, get_saved_ffprobe_path


def _from_env(var_name: str) -> Path | None:
    value = os.getenv(var_name)
    if not value:
        return None
    path = Path(value).expanduser()
    return path.resolve() if path.exists() else None


def _from_local(binary_name: str) -> Path | None:
    root = runtime_root()
    names = (binary_name, f"{binary_name}.exe")
    candidates: list[Path] = []

    for name in names:
        candidates.append(root / name)
        candidates.append(root / "bin" / name)
        candidates.append(root / "tools" / name)
        candidates.append(root / "tools" / "ffmpeg" / name)
        candidates.append(root / "third_party" / "ffmpeg" / name)

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return None


def _from_bundle(binary_name: str) -> Path | None:
    bundle = bundle_root()
    if bundle is None:
        return None

    names = (binary_name, f"{binary_name}.exe")
    candidates: list[Path] = []

    for name in names:
        candidates.append(bundle / name)
        candidates.append(bundle / "bin" / name)
        candidates.append(bundle / "tools" / name)
        candidates.append(bundle / "tools" / "ffmpeg" / name)
        candidates.append(bundle / "third_party" / "ffmpeg" / name)

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return None


def _from_path(binary_name: str) -> Path | None:
    lookup = shutil.which(binary_name) or shutil.which(f"{binary_name}.exe")
    return Path(lookup).resolve() if lookup else None


def locate_ffmpeg() -> Path | None:
    return (
        _from_env("FFMPEG_PATH")
        or get_saved_ffmpeg_path()
        or _from_bundle("ffmpeg")
        or _from_local("ffmpeg")
        or _from_path("ffmpeg")
    )


def locate_ffprobe() -> Path | None:
    return (
        _from_env("FFPROBE_PATH")
        or get_saved_ffprobe_path()
        or _from_bundle("ffprobe")
        or _from_local("ffprobe")
        or _from_path("ffprobe")
    )
