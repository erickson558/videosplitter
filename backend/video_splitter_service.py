"""Business logic for splitting a video into numbered parts."""

from __future__ import annotations

import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Callable

from .errors import FFmpegBinaryNotFoundError, SplitCancelledError, SplitExecutionError
from .ffmpeg_locator import locate_ffmpeg, locate_ffprobe
from .models import (
    EQUAL_PARTS_SPLIT_MODE,
    PROCESSING_DEVICE_AUTO,
    PROCESSING_DEVICE_CPU,
    PROCESSING_DEVICE_GPU_ALL,
    PROCESSING_DEVICE_GPU_AMF,
    PROCESSING_DEVICE_GPU_QSV,
    SplitJobConfig,
)

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

        self._available_h264_encoders = self._detect_available_h264_encoders()
        self._preferred_video_encoder = self._select_preferred_encoder(self._available_h264_encoders)
        self._cancel_requested = threading.Event()
        self._process_lock = threading.Lock()
        self._active_process: subprocess.Popen[str] | None = None

    def cancel_current_job(self) -> bool:
        """Request cancellation and terminate an active FFmpeg process when possible."""
        self._cancel_requested.set()
        with self._process_lock:
            process = self._active_process

        if process is None:
            return False

        if process.poll() is not None:
            return False

        process.terminate()
        return True

    @classmethod
    def detect_processing_options(cls, ffmpeg_path: Path | None = None) -> list[tuple[str, str]]:
        options: list[tuple[str, str]] = [
            (PROCESSING_DEVICE_AUTO, "Automatico (GPU si existe, sino CPU)"),
            (PROCESSING_DEVICE_CPU, "Solo CPU"),
        ]

        resolved_ffmpeg = ffmpeg_path or locate_ffmpeg()
        if resolved_ffmpeg is None:
            return options

        encoders_output = cls._read_encoders_output(resolved_ffmpeg)
        if not encoders_output:
            return options

        available = cls._available_h264_encoders_from_output(encoders_output)
        adapters = cls._detect_display_adapters()
        has_intel_gpu = any("intel" in name.lower() for name in adapters)
        has_amd_gpu = any(token in name.lower() for name in adapters for token in ("amd", "radeon"))

        if "h264_nvenc" in available:
            nvidia_gpus = cls._detect_nvidia_gpus()
            if nvidia_gpus:
                options.append((PROCESSING_DEVICE_GPU_ALL, f"GPU NVIDIA (todas: {len(nvidia_gpus)})"))
                for index, name in nvidia_gpus:
                    options.append((f"gpu_{index}", f"GPU NVIDIA {index}: {name}"))
            elif any("nvidia" in name.lower() for name in adapters):
                options.append((PROCESSING_DEVICE_GPU_ALL, "GPU NVIDIA (detectada)"))
            else:
                options.append((PROCESSING_DEVICE_GPU_ALL, "GPU NVIDIA (auto)"))

        if "h264_qsv" in available and has_intel_gpu:
            intel_name = cls._first_adapter_match(adapters, ("intel",))
            options.append((PROCESSING_DEVICE_GPU_QSV, f"GPU Intel QSV ({intel_name})"))

        if "h264_amf" in available and has_amd_gpu:
            amd_name = cls._first_adapter_match(adapters, ("amd", "radeon"))
            options.append((PROCESSING_DEVICE_GPU_AMF, f"GPU AMD AMF ({amd_name})"))

        return options

    def split_video(
        self,
        config: SplitJobConfig,
        progress_callback: ProgressCallback | None = None,
    ) -> list[Path]:
        self._cancel_requested.clear()
        validated = config.validated()
        duration_seconds = self._probe_duration(validated.input_video)
        split_points = self._build_split_points(validated, duration_seconds)

        if progress_callback:
            progress_callback(0.0, "Preparando division de video...")
            if duration_seconds is None:
                progress_callback(None, "No se pudo leer la duracion exacta del video.")

        self._raise_if_cancel_requested()

        output_pattern = (
            validated.output_dir
            / f"{validated.safe_output_stem} Parte %d{validated.output_extension}"
        )
        selected_encoder = self._resolve_video_encoder(validated.processing_device)
        command = self._build_command(
            validated,
            output_pattern,
            split_points,
            video_encoder=selected_encoder,
        )
        self._remove_existing_output_parts(validated)

        try:
            self._run_ffmpeg(command, duration_seconds, progress_callback)
        except SplitExecutionError:
            self._raise_if_cancel_requested()
            if selected_encoder == "libx264":
                raise

            if progress_callback:
                progress_callback(
                    None,
                    "Aceleracion por GPU no disponible en tiempo de ejecucion. Reintentando con CPU...",
                )

            self._remove_existing_output_parts(validated)
            cpu_command = self._build_command(
                validated,
                output_pattern,
                split_points,
                video_encoder="libx264",
            )
            self._run_ffmpeg(cpu_command, duration_seconds, progress_callback)

        self._raise_if_cancel_requested()
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
        video_encoder: str | None = None,
    ) -> list[str]:
        profile = config.output_profile
        container = config.container_profile
        gop = profile.fps * 2
        selected_encoder = video_encoder or self._resolve_video_encoder(config.processing_device)

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

        command.extend(["-r", str(profile.fps)])
        command.extend(self._video_encoder_args(selected_encoder, config.processing_device))
        command.extend(
            [
                "-pix_fmt",
                "yuv420p",
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

    def _detect_available_h264_encoders(self) -> set[str]:
        output = self._read_encoders_output(self.ffmpeg_path)
        if not output:
            return set()
        return self._available_h264_encoders_from_output(output)

    @staticmethod
    def _read_encoders_output(ffmpeg_path: Path) -> str:
        command = [
            str(ffmpeg_path),
            "-hide_banner",
            "-loglevel",
            "error",
            "-encoders",
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                **_hidden_process_kwargs(),
            )
        except OSError:
            return ""
        if result.returncode != 0:
            return ""
        return result.stdout

    @staticmethod
    def _available_h264_encoders_from_output(encoders_output: str) -> set[str]:
        normalized = encoders_output.lower()
        found: set[str] = set()
        for encoder in ("h264_nvenc", "h264_qsv", "h264_amf", "libx264"):
            if re.search(rf"\b{encoder}\b", normalized):
                found.add(encoder)
        return found

    @staticmethod
    def _select_preferred_encoder(available_encoders: set[str]) -> str:
        for encoder in ("h264_nvenc", "h264_qsv", "h264_amf"):
            if encoder in available_encoders:
                return encoder
        return "libx264"

    @staticmethod
    def _select_video_encoder(encoders_output: str) -> str:
        available = VideoSplitterService._available_h264_encoders_from_output(encoders_output)
        return VideoSplitterService._select_preferred_encoder(available)

    def _resolve_video_encoder(self, processing_device: str) -> str:
        if processing_device == PROCESSING_DEVICE_CPU:
            return "libx264"

        if processing_device.startswith("gpu_"):
            if processing_device == PROCESSING_DEVICE_GPU_QSV:
                return "h264_qsv" if "h264_qsv" in self._available_h264_encoders else "libx264"
            if processing_device == PROCESSING_DEVICE_GPU_AMF:
                return "h264_amf" if "h264_amf" in self._available_h264_encoders else "libx264"
            return "h264_nvenc" if "h264_nvenc" in self._available_h264_encoders else self._preferred_video_encoder

        if processing_device == PROCESSING_DEVICE_AUTO:
            return self._preferred_video_encoder

        return "libx264"

    @staticmethod
    def _video_encoder_args(video_encoder: str, processing_device: str) -> list[str]:
        if video_encoder == "h264_nvenc":
            args = ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "20"]
            if processing_device.startswith("gpu_") and processing_device not in {
                PROCESSING_DEVICE_GPU_ALL,
                PROCESSING_DEVICE_GPU_QSV,
                PROCESSING_DEVICE_GPU_AMF,
            }:
                gpu_index = processing_device[4:]
                if gpu_index.isdigit():
                    args.extend(["-gpu", gpu_index])
            return args
        if video_encoder == "h264_qsv":
            return ["-c:v", "h264_qsv", "-global_quality", "23"]
        if video_encoder == "h264_amf":
            return ["-c:v", "h264_amf", "-quality", "balanced"]
        return ["-c:v", "libx264", "-preset", "medium", "-crf", "20"]

    @staticmethod
    def _detect_nvidia_gpus() -> list[tuple[int, str]]:
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name",
                    "--format=csv,noheader",
                ],
                capture_output=True,
                text=True,
                check=False,
                **_hidden_process_kwargs(),
            )
        except OSError:
            return []
        if result.returncode != 0:
            return []

        entries: list[tuple[int, str]] = []
        for line in result.stdout.splitlines():
            raw = line.strip()
            if not raw:
                continue
            if "," not in raw:
                continue
            index_text, name = raw.split(",", 1)
            index_text = index_text.strip()
            if not index_text.isdigit():
                continue
            entries.append((int(index_text), name.strip()))
        return entries

    @staticmethod
    def _detect_display_adapters() -> list[str]:
        """Read installed display adapters from Windows when available."""
        if os.name != "nt":
            return []

        commands = [
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name",
            ],
            [
                "wmic",
                "path",
                "win32_videocontroller",
                "get",
                "name",
            ],
        ]

        for command in commands:
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=False,
                    **_hidden_process_kwargs(),
                )
            except OSError:
                continue

            if result.returncode != 0:
                continue

            adapters = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            filtered = [name for name in adapters if name.lower() != "name"]
            if filtered:
                return filtered

        return []

    @staticmethod
    def _first_adapter_match(adapters: list[str], tokens: tuple[str, ...]) -> str:
        for name in adapters:
            lowered = name.lower()
            if any(token in lowered for token in tokens):
                return name
        return "detectada"

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
        self._raise_if_cancel_requested()
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
        with self._process_lock:
            self._active_process = process

        if process.stdout is None:
            raise SplitExecutionError("No se pudo leer la salida de FFmpeg.")

        error_lines: list[str] = []

        try:
            for raw_line in process.stdout:
                self._raise_if_cancel_requested()
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
        finally:
            process.stdout.close()
            with self._process_lock:
                if self._active_process is process:
                    self._active_process = None

        return_code = process.wait()
        if self._cancel_requested.is_set() or return_code in {-15, -9}:  # pragma: no cover
            raise SplitCancelledError("Conversion cancelada por el usuario.")
        if return_code != 0:
            details = "\n".join(error_lines[-10:]).strip()
            message = details or f"FFmpeg termino con codigo {return_code}."
            raise SplitExecutionError(message)

    def _raise_if_cancel_requested(self) -> None:
        if self._cancel_requested.is_set():
            raise SplitCancelledError("Conversion cancelada por el usuario.")

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

    def _remove_existing_output_parts(self, config: SplitJobConfig) -> None:
        for output_file in self._collect_output_parts(config):
            try:
                output_file.unlink()
            except OSError:
                continue

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
