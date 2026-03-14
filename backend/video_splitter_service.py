"""Business logic for splitting a video into numbered parts."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Callable

from .errors import FFmpegBinaryNotFoundError, SplitExecutionError
from .ffmpeg_locator import locate_ffmpeg, locate_ffprobe
from .models import EQUAL_PARTS_SPLIT_MODE, SplitJobConfig

ProgressCallback = Callable[[float | None, str], None]


def _hidden_process_kwargs() -> dict[str, object]:
    """Hide Windows console windows for child processes."""
    if os.name != "nt":
        return {}

    kwargs: dict[str, object] = {}
    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if create_no_window:
        kwargs["creationflags"] = create_no_window

    startup_cls = getattr(subprocess, "STARTUPINFO", None)
    if startup_cls is not None:
        startupinfo = startup_cls()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
        startupinfo.wShowWindow = 0
        kwargs["startupinfo"] = startupinfo

    return kwargs


class VideoSplitterService:
    """Coordinates FFmpeg execution and output discovery."""

    def __init__(self, ffmpeg_path: Path | None = None, ffprobe_path: Path | None = None) -> None:
        self.ffmpeg_path = ffmpeg_path or locate_ffmpeg()
        self.ffprobe_path = ffprobe_path or locate_ffprobe()

        if self.ffmpeg_path is None:
            raise FFmpegBinaryNotFoundError(
                "No se encontro FFmpeg. Instalalo o define la variable FFMPEG_PATH."
            )

    def split_video(
        self,
        config: SplitJobConfig,
        progress_callback: ProgressCallback | None = None,
    ) -> list[Path]:
        validated = config.validated()
        duration_seconds = self._probe_duration(validated.input_video)
        split_points = self._build_split_points(validated, duration_seconds)

        if progress_callback:
            progress_callback(0.0, "Preparando division de video...")
            if duration_seconds is None:
                progress_callback(None, "No se pudo leer la duracion exacta del video.")

        output_pattern = (
            validated.output_dir
            / f"{validated.safe_output_stem} Parte %d{validated.output_extension}"
        )
        command = self._build_command(validated, output_pattern, split_points)
        self._run_ffmpeg(command, duration_seconds, progress_callback)

        output_parts = self._collect_output_parts(validated)
        if not output_parts:
            raise SplitExecutionError("FFmpeg finalizo sin generar archivos de salida.")

        if progress_callback:
            progress_callback(100.0, f"Completado: {len(output_parts)} partes generadas.")

        return output_parts

    def _build_command(
        self,
        config: SplitJobConfig,
        output_pattern: Path,
        split_points: list[float] | None,
    ) -> list[str]:
        profile = config.output_profile
        container = config.container_profile
        gop = profile.fps * 2

        command = [
            str(self.ffmpeg_path),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(config.input_video),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
        ]

        if profile.width is not None and profile.height is not None:
            video_filter = (
                f"scale={profile.width}:{profile.height}:force_original_aspect_ratio=increase,"
                f"crop={profile.width}:{profile.height},setsar=1"
            )
            command.extend(["-vf", video_filter])

        command.extend(
            [
                "-r",
                str(profile.fps),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ar",
                "48000",
                "-g",
                str(gop),
                "-keyint_min",
                str(gop),
                "-sc_threshold",
                "0",
                "-f",
                "segment",
                "-reset_timestamps",
                "1",
                "-segment_start_number",
                "1",
                "-segment_format",
                container.muxer,
            ]
        )

        if split_points:
            split_points_arg = ",".join(self._format_ffmpeg_seconds(value) for value in split_points)
            command.extend(["-force_key_frames", split_points_arg, "-segment_times", split_points_arg])
        else:
            segment_seconds = self._format_ffmpeg_seconds(float(config.segment_seconds))
            command.extend(
                [
                    "-force_key_frames",
                    f"expr:gte(t,n_forced*{segment_seconds})",
                    "-segment_time",
                    segment_seconds,
                ]
            )

        if container.muxer in {"mp4", "mov"}:
            command.extend(["-segment_format_options", "movflags=+faststart"])

        command.extend(["-progress", "pipe:1", "-nostats", str(output_pattern)])
        return command

    def _build_split_points(
        self,
        config: SplitJobConfig,
        duration_seconds: float | None,
    ) -> list[float] | None:
        if config.split_mode != EQUAL_PARTS_SPLIT_MODE:
            return None

        if duration_seconds is None or duration_seconds <= 0:
            raise SplitExecutionError(
                "No se pudo determinar la duracion del video para dividirlo en partes iguales."
            )

        return [
            (duration_seconds * index) / config.equal_parts_count
            for index in range(1, config.equal_parts_count)
        ]

    def _run_ffmpeg(
        self,
        command: list[str],
        duration_seconds: float | None,
        progress_callback: ProgressCallback | None,
    ) -> None:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **_hidden_process_kwargs(),
        )

        if process.stdout is None:
            raise SplitExecutionError("No se pudo leer la salida de FFmpeg.")

        error_lines: list[str] = []

        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue

            if "=" not in line:
                error_lines.append(line)
                continue

            key, value = line.split("=", 1)
            if key in {"out_time_ms", "out_time_us", "out_time"} and duration_seconds and progress_callback:
                current_seconds = self._progress_seconds(key, value)
                if current_seconds is None:
                    continue
                percent = min((current_seconds / duration_seconds) * 100.0, 99.9)
                progress_callback(
                    percent,
                    f"Procesando: {self._format_seconds(current_seconds)} / "
                    f"{self._format_seconds(duration_seconds)}",
                )
            elif key == "progress" and value == "end" and progress_callback:
                progress_callback(99.9, "Finalizando archivos de salida...")

        return_code = process.wait()
        if return_code != 0:
            details = "\n".join(error_lines[-10:]).strip()
            message = details or f"FFmpeg termino con codigo {return_code}."
            raise SplitExecutionError(message)

    def _probe_duration(self, input_video: Path) -> float | None:
        if self.ffprobe_path is None:
            return None

        command = [
            str(self.ffprobe_path),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(input_video),
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            **_hidden_process_kwargs(),
        )
        if result.returncode != 0:
            return None

        value = result.stdout.strip()
        if not value:
            return None

        try:
            duration = float(value)
        except ValueError:
            return None

        return duration if duration > 0 else None

    def _collect_output_parts(self, config: SplitJobConfig) -> list[Path]:
        escaped_name = re.escape(config.safe_output_stem)
        escaped_ext = re.escape(config.output_extension)
        matcher = re.compile(rf"^{escaped_name} Parte (\d+){escaped_ext}$")

        parts: list[tuple[int, Path]] = []
        for file in config.output_dir.iterdir():
            if not file.is_file():
                continue
            match = matcher.match(file.name)
            if not match:
                continue
            parts.append((int(match.group(1)), file))

        parts.sort(key=lambda item: item[0])
        return [path for _, path in parts]

    @staticmethod
    def _progress_seconds(key: str, value: str) -> float | None:
        cleaned = value.strip()
        if not cleaned or cleaned.upper() == "N/A":
            return None

        if key in {"out_time_ms", "out_time_us"}:
            try:
                raw = float(cleaned)
            except ValueError:
                return None
            return max(raw / 1_000_000.0, 0.0)

        if key == "out_time":
            parts = cleaned.split(":")
            if len(parts) != 3:
                return None
            try:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = float(parts[2])
            except ValueError:
                return None
            return max((hours * 3600) + (minutes * 60) + seconds, 0.0)

        return None

    @staticmethod
    def _format_seconds(total_seconds: float) -> str:
        rounded = int(total_seconds)
        hours, remainder = divmod(rounded, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    @staticmethod
    def _format_ffmpeg_seconds(total_seconds: float) -> str:
        return f"{max(total_seconds, 0.001):.6f}".rstrip("0").rstrip(".")
