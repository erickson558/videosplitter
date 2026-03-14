"""Data models used by the video splitter backend."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import InvalidSplitConfigError
from .output_formats import (
    CONTAINER_FORMATS,
    DEFAULT_CONTAINER_FORMAT,
    DEFAULT_VIDEO_PROFILE,
    VIDEO_PROFILES,
    ContainerFormat,
    VideoProfile,
)

SECONDS_SPLIT_MODE = "seconds"
EQUAL_PARTS_SPLIT_MODE = "equal_parts"
DEFAULT_SPLIT_MODE = SECONDS_SPLIT_MODE


@dataclass(frozen=True, slots=True)
class SplitJobConfig:
    """Immutable split configuration validated before execution."""

    input_video: Path
    output_dir: Path
    split_mode: str = DEFAULT_SPLIT_MODE
    segment_seconds: int = 60
    equal_parts_count: int = 2
    video_profile: str = DEFAULT_VIDEO_PROFILE
    container_format: str = DEFAULT_CONTAINER_FORMAT

    def validated(self) -> "SplitJobConfig":
        input_path = self.input_video.expanduser().resolve()
        output_path = self.output_dir.expanduser().resolve()

        if not input_path.exists() or not input_path.is_file():
            raise InvalidSplitConfigError("El archivo de video seleccionado no existe.")

        if self.split_mode not in {SECONDS_SPLIT_MODE, EQUAL_PARTS_SPLIT_MODE}:
            raise InvalidSplitConfigError("El modo de division seleccionado no es valido.")

        if self.split_mode == SECONDS_SPLIT_MODE and self.segment_seconds <= 0:
            raise InvalidSplitConfigError("El tiempo por parte debe ser mayor a 0.")

        if self.split_mode == EQUAL_PARTS_SPLIT_MODE and self.equal_parts_count <= 1:
            raise InvalidSplitConfigError("La cantidad de partes iguales debe ser mayor a 1.")

        if self.video_profile not in VIDEO_PROFILES:
            raise InvalidSplitConfigError("El perfil de video seleccionado no es valido.")

        if self.container_format not in CONTAINER_FORMATS:
            raise InvalidSplitConfigError("El contenedor de salida seleccionado no es valido.")

        profile = VIDEO_PROFILES[self.video_profile]
        container = CONTAINER_FORMATS[self.container_format]

        if profile.fps <= 0:
            raise InvalidSplitConfigError("Los FPS de salida deben ser mayores a 0.")

        if profile.width is not None and profile.width <= 0:
            raise InvalidSplitConfigError("El ancho de salida debe ser mayor a 0.")

        if profile.height is not None and profile.height <= 0:
            raise InvalidSplitConfigError("El alto de salida debe ser mayor a 0.")

        output_path.mkdir(parents=True, exist_ok=True)

        return SplitJobConfig(
            input_video=input_path,
            output_dir=output_path,
            split_mode=self.split_mode,
            segment_seconds=self.segment_seconds,
            equal_parts_count=self.equal_parts_count,
            video_profile=profile.key,
            container_format=container.key,
        )

    @property
    def output_extension(self) -> str:
        return self.container_profile.extension

    @property
    def output_profile(self) -> VideoProfile:
        return VIDEO_PROFILES[self.video_profile]

    @property
    def container_profile(self) -> ContainerFormat:
        return CONTAINER_FORMATS[self.container_format]

    @property
    def safe_output_stem(self) -> str:
        stem = self.input_video.stem.replace("%", "_")
        return stem or "video"
