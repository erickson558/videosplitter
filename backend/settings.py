"""Persistent application settings."""

from __future__ import annotations

import json
from pathlib import Path

from app_metadata import APP_VERSION
from .models import (
    DEFAULT_PROCESSING_DEVICE,
    DEFAULT_SPLIT_MODE,
    EQUAL_PARTS_SPLIT_MODE,
    SECONDS_SPLIT_MODE,
)
from .output_formats import DEFAULT_CONTAINER_FORMAT, DEFAULT_VIDEO_PROFILE
from .runtime_paths import runtime_root

_SETTINGS_FILE_NAME = "videosplitter.settings.json"


def settings_file_path() -> Path:
    return runtime_root() / _SETTINGS_FILE_NAME


def load_settings() -> dict[str, object]:
    path = settings_file_path()
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}

    if not isinstance(payload, dict):
        return {}

    return payload


def _write_settings(payload: dict[str, object]) -> None:
    payload["app_version"] = APP_VERSION
    path = settings_file_path()
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _read_string(payload: dict[str, object], key: str, default: str = "") -> str:
    value = payload.get(key)
    if isinstance(value, str):
        return value.strip()
    return default


def _read_positive_int(payload: dict[str, object], key: str, default: int) -> int:
    value = payload.get(key)
    if isinstance(value, bool):
        return default
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str):
        try:
            parsed = int(value.strip())
        except ValueError:
            return default
        return parsed if parsed > 0 else default
    return default


def get_ui_settings() -> dict[str, object]:
    payload = load_settings()
    split_mode = _read_string(payload, "split_mode", DEFAULT_SPLIT_MODE)
    if split_mode not in {SECONDS_SPLIT_MODE, EQUAL_PARTS_SPLIT_MODE}:
        split_mode = DEFAULT_SPLIT_MODE

    video_profile = _read_string(payload, "video_profile", DEFAULT_VIDEO_PROFILE) or DEFAULT_VIDEO_PROFILE
    container_format = _read_string(payload, "container_format", DEFAULT_CONTAINER_FORMAT) or DEFAULT_CONTAINER_FORMAT

    return {
        "language": _read_string(payload, "language", "es") or "es",
        "input_video": _read_string(payload, "input_video"),
        "split_mode": split_mode,
        "segment_seconds": _read_positive_int(payload, "segment_seconds", 60),
        "equal_parts_count": _read_positive_int(payload, "equal_parts_count", 2),
        "video_profile": video_profile,
        "container_format": container_format,
        "processing_device": _read_string(payload, "processing_device", DEFAULT_PROCESSING_DEVICE)
        or DEFAULT_PROCESSING_DEVICE,
        "output_dir": _read_string(payload, "output_dir"),
    }


def save_ffmpeg_settings(ffmpeg_path: Path, ffprobe_path: Path | None = None) -> None:
    payload = load_settings()
    payload["ffmpeg_path"] = str(ffmpeg_path.resolve())
    if ffprobe_path:
        payload["ffprobe_path"] = str(ffprobe_path.resolve())

    _write_settings(payload)


def save_ui_settings(
    *,
    language: str,
    input_video: str,
    split_mode: str,
    segment_seconds: int,
    equal_parts_count: int,
    video_profile: str,
    container_format: str,
    processing_device: str,
    output_dir: str,
) -> None:
    payload = load_settings()
    payload.update(
        {
            "language": language.strip().lower() or "es",
            "input_video": input_video.strip(),
            "split_mode": split_mode,
            "segment_seconds": max(int(segment_seconds), 1),
            "equal_parts_count": max(int(equal_parts_count), 1),
            "video_profile": video_profile,
            "container_format": container_format,
            "processing_device": processing_device.strip() or DEFAULT_PROCESSING_DEVICE,
            "output_dir": output_dir.strip(),
        }
    )
    _write_settings(payload)


def get_saved_ffmpeg_path() -> Path | None:
    value = _read_string(load_settings(), "ffmpeg_path")
    if not value:
        return None
    path = Path(value).expanduser()
    return path.resolve() if path.exists() else None


def get_saved_ffprobe_path() -> Path | None:
    value = _read_string(load_settings(), "ffprobe_path")
    if not value:
        return None
    path = Path(value).expanduser()
    return path.resolve() if path.exists() else None

