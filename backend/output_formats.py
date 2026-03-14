"""Output format and video profile definitions for generated parts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VideoProfile:
    """Resize/FPS profile selected from the UI."""

    key: str
    label: str
    width: int | None
    height: int | None
    fps: int


@dataclass(frozen=True, slots=True)
class ContainerFormat:
    """Container/extension selected from the UI."""

    key: str
    label: str
    extension: str
    muxer: str


DEFAULT_VIDEO_PROFILE = "short_9_16"
DEFAULT_CONTAINER_FORMAT = "mp4"

VIDEO_PROFILE_ORDER: tuple[str, ...] = (
    "short_9_16",
    "normal_16_9",
    "original",
)

VIDEO_PROFILES: dict[str, VideoProfile] = {
    "short_9_16": VideoProfile(
        key="short_9_16",
        label="Short 9:16 (1080x1920)",
        width=1080,
        height=1920,
        fps=30,
    ),
    "normal_16_9": VideoProfile(
        key="normal_16_9",
        label="Normal 16:9 (1920x1080)",
        width=1920,
        height=1080,
        fps=30,
    ),
    "original": VideoProfile(
        key="original",
        label="Original (sin redimensionar)",
        width=None,
        height=None,
        fps=30,
    ),
}

CONTAINER_FORMAT_ORDER: tuple[str, ...] = (
    "mp4",
    "mkv",
    "mov",
)

CONTAINER_FORMATS: dict[str, ContainerFormat] = {
    "mp4": ContainerFormat(
        key="mp4",
        label="MP4",
        extension=".mp4",
        muxer="mp4",
    ),
    "mkv": ContainerFormat(
        key="mkv",
        label="MKV",
        extension=".mkv",
        muxer="matroska",
    ),
    "mov": ContainerFormat(
        key="mov",
        label="MOV",
        extension=".mov",
        muxer="mov",
    ),
}


def iter_video_profiles() -> list[VideoProfile]:
    """Return video profiles in deterministic UI order."""
    return [VIDEO_PROFILES[key] for key in VIDEO_PROFILE_ORDER]


def iter_container_formats() -> list[ContainerFormat]:
    """Return container formats in deterministic UI order."""
    return [CONTAINER_FORMATS[key] for key in CONTAINER_FORMAT_ORDER]

