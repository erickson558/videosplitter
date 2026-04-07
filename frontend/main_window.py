"""Tkinter GUI for the video splitter application."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:  # pragma: no cover
    DND_FILES = None
    TkinterDnD = None

from app_metadata import APP_TITLE
from backend.errors import FFmpegBinaryNotFoundError, SplitCancelledError, VideoSplitterError
from backend.models import (
    DEFAULT_PROCESSING_DEVICE,
    DEFAULT_SPLIT_MODE,
    EQUAL_PARTS_SPLIT_MODE,
    SECONDS_SPLIT_MODE,
    SplitJobConfig,
)
from backend.output_formats import (
    CONTAINER_FORMATS,
    DEFAULT_CONTAINER_FORMAT,
    DEFAULT_VIDEO_PROFILE,
    VIDEO_PROFILES,
    iter_container_formats,
    iter_video_profiles,
)
from backend.settings import (
    get_saved_ffmpeg_path,
    get_ui_settings,
    save_ffmpeg_settings,
    save_ui_settings,
)
from backend.video_splitter_service import VideoSplitterService


SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".m4v", ".webm"}


def create_root_window() -> tk.Tk:
    """Create a Tk root with drag-and-drop support when available."""
    if TkinterDnD is not None:
        return TkinterDnD.Tk()
    return tk.Tk()


class VideoSplitterApp:
    """Desktop UI that orchestrates video splitting jobs."""

    _POLL_INTERVAL_MS = 120

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("860x560")
        self.root.minsize(820, 520)

        saved_ui_settings = get_ui_settings()

        self.video_var = tk.StringVar()
        self.output_var = tk.StringVar(value=str(saved_ui_settings["output_dir"]))
        self.split_mode_var = tk.StringVar(value=str(saved_ui_settings["split_mode"]))
        self.segment_var = tk.StringVar(value=str(saved_ui_settings["segment_seconds"]))
        self.equal_parts_var = tk.StringVar(value=str(saved_ui_settings["equal_parts_count"]))
        self.video_profile_var = tk.StringVar(
            value=str(saved_ui_settings["video_profile"] or DEFAULT_VIDEO_PROFILE)
        )
        self.container_format_var = tk.StringVar(
            value=str(saved_ui_settings["container_format"] or DEFAULT_CONTAINER_FORMAT)
        )
        self.processing_device_var = tk.StringVar(
            value=str(saved_ui_settings.get("processing_device", DEFAULT_PROCESSING_DEVICE))
        )

        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._worker: threading.Thread | None = None
        self._active_service: VideoSplitterService | None = None
        self._service_lock = threading.Lock()
        self._progress_indeterminate = False
        self._controls: list[tk.Widget] = []
        self._processing_options: list[tuple[str, str]] = []
        self._processing_label_to_value: dict[str, str] = {}
        self._processing_value_to_label: dict[str, str] = {}
        self._initialize_processing_options()

        self.status_var = tk.StringVar(value=self._initial_status_text())
        self.progress_var = tk.DoubleVar(value=0.0)
        self.processed_percent_var = tk.StringVar(value="Procesado: 0.0%")
        self.pending_percent_var = tk.StringVar(value="Pendiente: 100.0%")

        self._configure_styles()

        self._build_layout()
        self.root.after(self._POLL_INTERVAL_MS, self._flush_events)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.root.configure(bg="#f3f7fb")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Header.TFrame", background="#0e7490")
        style.configure("HeaderTitle.TLabel", background="#0e7490", foreground="#f0fdfa", font=("Segoe UI", 16, "bold"))
        style.configure("HeaderSub.TLabel", background="#0e7490", foreground="#ccfbf1", font=("Segoe UI", 10))
        style.configure("DropZone.TLabel", background="#e6fffb", foreground="#0f172a", padding=10, relief="solid")
        style.configure("Metric.TLabel", background="#ffffff", foreground="#0f172a", font=("Segoe UI", 10, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#0891b2")])

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=0, style="Card.TFrame")
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)

        header = ttk.Frame(container, padding=(18, 16), style="Header.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="VideoSplitter", style="HeaderTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Divide videos por segundos o partes iguales con GPU/CPU y cancelacion segura.",
            style="HeaderSub.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        body = ttk.Frame(container, padding=16, style="Card.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(1, weight=1)

        ttk.Label(body, text="Video").grid(row=0, column=0, sticky="w", pady=(0, 10))
        video_entry = ttk.Entry(body, textvariable=self.video_var)
        video_entry.grid(row=0, column=1, sticky="ew", pady=(0, 10), padx=(10, 10))
        video_button = ttk.Button(body, text="Buscar...", command=self._select_video)
        video_button.grid(row=0, column=2, sticky="ew", pady=(0, 10))

        self.drop_zone = ttk.Label(
            body,
            text="Arrastra y suelta aqui un archivo de video",
            style="DropZone.TLabel",
            anchor="center",
        )
        self.drop_zone.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 12))
        self._register_drop_target()

        ttk.Label(body, text="Salida").grid(row=2, column=0, sticky="w", pady=(0, 10))
        output_entry = ttk.Entry(body, textvariable=self.output_var)
        output_entry.grid(row=2, column=1, sticky="ew", pady=(0, 10), padx=(10, 10))
        output_button = ttk.Button(body, text="Carpeta...", command=self._select_output_dir)
        output_button.grid(row=2, column=2, sticky="ew", pady=(0, 10))

        ttk.Label(body, text="Modo de division").grid(row=3, column=0, sticky="nw", pady=(0, 10))
        split_mode_frame = ttk.Frame(body)
        split_mode_frame.grid(row=3, column=1, columnspan=2, sticky="w", pady=(0, 10), padx=(10, 0))
        split_mode_buttons = [
            ttk.Radiobutton(
                split_mode_frame,
                text="Por segundos",
                value=SECONDS_SPLIT_MODE,
                variable=self.split_mode_var,
                command=self._on_split_mode_changed,
            ),
            ttk.Radiobutton(
                split_mode_frame,
                text="Partes iguales",
                value=EQUAL_PARTS_SPLIT_MODE,
                variable=self.split_mode_var,
                command=self._on_split_mode_changed,
            ),
        ]
        for index, button in enumerate(split_mode_buttons):
            button.grid(row=0, column=index, sticky="w", padx=(0, 18))

        ttk.Label(body, text="Segundos por parte").grid(row=4, column=0, sticky="w", pady=(0, 10))
        self.segment_entry = ttk.Entry(body, textvariable=self.segment_var, width=8)
        self.segment_entry.grid(row=4, column=1, sticky="w", pady=(0, 10), padx=(10, 10))

        ttk.Label(body, text="Cantidad de partes").grid(row=5, column=0, sticky="w", pady=(0, 10))
        self.equal_parts_entry = ttk.Spinbox(body, from_=2, to=999, textvariable=self.equal_parts_var, width=8)
        self.equal_parts_entry.grid(row=5, column=1, sticky="w", pady=(0, 10), padx=(10, 10))

        ttk.Label(body, text="Perfil de video").grid(row=6, column=0, sticky="nw", pady=(0, 8))
        video_profiles_frame = ttk.Frame(body)
        video_profiles_frame.grid(row=6, column=1, columnspan=2, sticky="ew", pady=(0, 10), padx=(10, 0))
        profile_buttons: list[ttk.Radiobutton] = []

        for profile in iter_video_profiles():
            button = ttk.Radiobutton(
                video_profiles_frame,
                text=profile.label,
                value=profile.key,
                variable=self.video_profile_var,
                command=self._on_format_changed,
            )
            button.pack(anchor="w")
            profile_buttons.append(button)

        ttk.Label(body, text="Contenedor").grid(row=7, column=0, sticky="nw", pady=(0, 12))
        containers_frame = ttk.Frame(body)
        containers_frame.grid(row=7, column=1, columnspan=2, sticky="ew", pady=(0, 12), padx=(10, 0))
        container_buttons: list[ttk.Radiobutton] = []
        for format_item in iter_container_formats():
            button = ttk.Radiobutton(
                containers_frame,
                text=format_item.label,
                value=format_item.key,
                variable=self.container_format_var,
                command=self._on_format_changed,
            )
            button.pack(side="left", padx=(0, 16))
            container_buttons.append(button)

        ttk.Label(body, text="Procesamiento").grid(row=8, column=0, sticky="w", pady=(0, 12))
        self.processing_combo = ttk.Combobox(body, state="readonly", width=42)
        self.processing_combo.grid(row=8, column=1, columnspan=2, sticky="w", pady=(0, 12), padx=(10, 0))
        self._refresh_processing_combobox()
        self.processing_combo.bind("<<ComboboxSelected>>", self._on_processing_device_changed)

        self.progress_bar = ttk.Progressbar(
            body,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
        )
        self.progress_bar.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(0, 8))

        metrics_frame = ttk.Frame(body, style="Card.TFrame")
        metrics_frame.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        metrics_frame.columnconfigure((0, 1), weight=1)
        ttk.Label(metrics_frame, textvariable=self.processed_percent_var, style="Metric.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(metrics_frame, textvariable=self.pending_percent_var, style="Metric.TLabel").grid(
            row=0, column=1, sticky="e"
        )

        status_label = ttk.Label(body, textvariable=self.status_var)
        status_label.grid(row=11, column=0, columnspan=3, sticky="w", pady=(0, 14))

        self.start_button = ttk.Button(
            body,
            text="Dividir Video",
            command=self._start_job,
            style="Accent.TButton",
        )
        self.start_button.grid(row=12, column=0, sticky="ew", padx=(0, 10))

        self.cancel_button = ttk.Button(
            body,
            text="Cancelar",
            command=self._cancel_job,
            state="disabled",
        )
        self.cancel_button.grid(row=12, column=1, sticky="ew", padx=(0, 10))

        self.ffmpeg_button = ttk.Button(
            body,
            text="Configurar FFmpeg...",
            command=self._configure_ffmpeg,
        )
        self.ffmpeg_button.grid(row=12, column=2, sticky="ew")

        for entry in (output_entry, self.segment_entry, self.equal_parts_entry):
            entry.bind("<FocusOut>", self._persist_ui_settings_event)
            entry.bind("<Return>", self._persist_ui_settings_event)

        self._controls = [
            video_entry,
            video_button,
            output_entry,
            output_button,
            *split_mode_buttons,
            self.segment_entry,
            self.equal_parts_entry,
            *profile_buttons,
            *container_buttons,
            self.processing_combo,
            self.ffmpeg_button,
        ]
        self._sync_split_mode_controls()

    def _register_drop_target(self) -> None:
        if DND_FILES is None:
            self.drop_zone.configure(text="Arrastrar y soltar no disponible. Instala tkinterdnd2 para habilitarlo.")
            return

        # Bind drag-and-drop to both zone and root for better UX.
        for target in (self.drop_zone, self.root):
            try:
                target.drop_target_register(DND_FILES)
                target.dnd_bind("<<Drop>>", self._on_drop_file)
            except tk.TclError:
                continue

    def _on_drop_file(self, event: tk.Event[tk.Misc]) -> None:
        if self._worker and self._worker.is_alive():
            return

        dropped_path = self._extract_first_dropped_path(getattr(event, "data", ""))
        if dropped_path is None:
            self.status_var.set("No se detecto un archivo valido en el arrastre.")
            return

        self._apply_video_selection(dropped_path)
        self.status_var.set(
            f"Video cargado por arrastre. Modo: {self._selected_split_mode_label()}. "
            f"Formato activo: {self._selected_format_label()}."
        )

    def _extract_first_dropped_path(self, data: str) -> Path | None:
        if not data:
            return None

        # Tk may return a list with braces for paths containing spaces.
        for raw_item in self.root.tk.splitlist(data):
            item = raw_item.strip().strip("{}\"")
            if not item:
                continue
            candidate = Path(item)
            if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                return candidate
        return None

    def _cancel_job(self) -> None:
        with self._service_lock:
            service = self._active_service

        if service is None:
            return

        service.cancel_current_job()
        self.status_var.set("Cancelando conversion y liberando FFmpeg...")
        self.cancel_button.configure(state="disabled")

    def _initialize_processing_options(self) -> None:
        options = VideoSplitterService.detect_processing_options(get_saved_ffmpeg_path())
        self._processing_options = options
        self._processing_label_to_value = {label: value for value, label in options}
        self._processing_value_to_label = {value: label for value, label in options}

        selected_value = self.processing_device_var.get().strip() or DEFAULT_PROCESSING_DEVICE
        if selected_value not in self._processing_value_to_label:
            selected_value = DEFAULT_PROCESSING_DEVICE
        self.processing_device_var.set(selected_value)

    def _refresh_processing_combobox(self) -> None:
        labels = [label for _, label in self._processing_options]
        self.processing_combo.configure(values=labels)
        selected_label = self._processing_value_to_label.get(
            self.processing_device_var.get(),
            self._processing_value_to_label[DEFAULT_PROCESSING_DEVICE],
        )
        self.processing_combo.set(selected_label)

    def _initial_status_text(self) -> str:
        ffmpeg_ready = get_saved_ffmpeg_path() is not None
        base = "FFmpeg configurado" if ffmpeg_ready else "FFmpeg incluido automaticamente"
        return (
            f"{base}. Modo: {self._selected_split_mode_label()}. "
            f"Formato activo: {self._selected_format_label()}. "
            f"Procesamiento: {self._selected_processing_label()}."
        )

    def _selected_split_mode_label(self) -> str:
        if self.split_mode_var.get() == EQUAL_PARTS_SPLIT_MODE:
            return "partes iguales"
        return "por segundos"

    def _selected_format_label(self) -> str:
        video_profile = VIDEO_PROFILES.get(self.video_profile_var.get())
        if video_profile is None:
            video_profile = VIDEO_PROFILES[DEFAULT_VIDEO_PROFILE]

        container = CONTAINER_FORMATS.get(self.container_format_var.get())
        if container is None:
            container = CONTAINER_FORMATS[DEFAULT_CONTAINER_FORMAT]

        return f"{video_profile.label} + {container.label}"

    def _selected_processing_label(self) -> str:
        processing_value_to_label = getattr(self, "_processing_value_to_label", {})
        selected_value = self.processing_device_var.get().strip() or DEFAULT_PROCESSING_DEVICE
        default_label = processing_value_to_label.get(
            DEFAULT_PROCESSING_DEVICE,
            "Automatico (GPU si existe, sino CPU)",
        )
        return processing_value_to_label.get(selected_value, default_label)

    def _on_format_changed(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._persist_ui_settings()
        self.status_var.set(
            f"Modo: {self._selected_split_mode_label()}. Formato activo: {self._selected_format_label()}."
            f" Procesamiento: {self._selected_processing_label()}."
        )

    def _on_split_mode_changed(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._sync_split_mode_controls()
        self._persist_ui_settings()
        self.status_var.set(
            f"Modo: {self._selected_split_mode_label()}. Formato activo: {self._selected_format_label()}."
            f" Procesamiento: {self._selected_processing_label()}."
        )

    def _on_processing_device_changed(self, _event: tk.Event[tk.Misc]) -> None:
        if self._worker and self._worker.is_alive():
            return

        selected_label = self.processing_combo.get().strip()
        selected_value = self._processing_label_to_value.get(selected_label, DEFAULT_PROCESSING_DEVICE)
        self.processing_device_var.set(selected_value)
        self._persist_ui_settings()
        self.status_var.set(
            f"Modo: {self._selected_split_mode_label()}. Formato activo: {self._selected_format_label()}."
            f" Procesamiento: {self._selected_processing_label()}."
        )

    def _select_video(self) -> None:
        selected = filedialog.askopenfilename(
            title="Selecciona un video",
            filetypes=[
                ("Videos", "*.mp4 *.mkv *.mov *.avi *.wmv *.flv *.m4v *.webm"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if not selected:
            return

        self._apply_video_selection(Path(selected))

    def _apply_video_selection(self, video_path: Path) -> None:
        self.video_var.set(str(video_path))
        if not self.output_var.get().strip():
            self.output_var.set(str(video_path.parent))
        self._persist_ui_settings()

    def _select_output_dir(self) -> None:
        selected = filedialog.askdirectory(title="Selecciona carpeta de salida")
        if selected:
            self.output_var.set(selected)
            self._persist_ui_settings()

    def _configure_ffmpeg(self) -> None:
        self._prompt_and_save_ffmpeg()

    def _prompt_and_save_ffmpeg(self) -> bool:
        selected = filedialog.askopenfilename(
            title="Selecciona ffmpeg.exe",
            filetypes=[
                ("FFmpeg ejecutable", "ffmpeg.exe"),
                ("Ejecutables", "*.exe"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if not selected:
            return False

        ffmpeg_path = Path(selected).resolve()
        name = ffmpeg_path.name.lower()
        if "ffmpeg" not in name:
            should_continue = messagebox.askyesno(
                "Confirmacion",
                "El archivo no parece ser ffmpeg.exe.\nDeseas usarlo de todas formas?",
                parent=self.root,
            )
            if not should_continue:
                return False

        ffprobe_path = ffmpeg_path.with_name("ffprobe.exe")
        save_ffmpeg_settings(
            ffmpeg_path=ffmpeg_path,
            ffprobe_path=(ffprobe_path if ffprobe_path.exists() else None),
        )
        self._initialize_processing_options()
        self._refresh_processing_combobox()
        self.status_var.set(
            f"FFmpeg configurado manualmente. Formato activo: {self._selected_format_label()}."
            f" Procesamiento: {self._selected_processing_label()}."
        )
        return True

    def _start_job(self) -> None:
        if self._worker and self._worker.is_alive():
            return

        try:
            config = self._build_config()
        except VideoSplitterError as exc:
            messagebox.showerror("Configuracion invalida", str(exc), parent=self.root)
            return

        self.progress_var.set(0.0)
        self.status_var.set("Iniciando proceso...")
        self._set_running_state(True)

        self._worker = threading.Thread(
            target=self._run_split_job,
            args=(config,),
            daemon=True,
        )
        self._worker.start()

    def _build_config(self) -> SplitJobConfig:
        video_raw = self.video_var.get().strip()
        output_raw = self.output_var.get().strip()
        split_mode = self.split_mode_var.get().strip() or DEFAULT_SPLIT_MODE
        segment_raw = self.segment_var.get().strip()
        equal_parts_raw = self.equal_parts_var.get().strip()
        video_profile = self.video_profile_var.get().strip()
        container_format = self.container_format_var.get().strip()
        processing_device = self.processing_device_var.get().strip() or DEFAULT_PROCESSING_DEVICE

        if not video_raw:
            raise VideoSplitterError("Debes seleccionar un video.")
        if not output_raw:
            raise VideoSplitterError("Debes seleccionar la carpeta de salida.")

        if split_mode == EQUAL_PARTS_SPLIT_MODE:
            try:
                equal_parts_count = int(equal_parts_raw)
            except ValueError as exc:
                raise VideoSplitterError("La cantidad de partes debe ser un numero entero.") from exc
            segment_seconds = max(self._parse_positive_int(segment_raw, 60), 1)
        else:
            try:
                segment_seconds = int(segment_raw)
            except ValueError as exc:
                raise VideoSplitterError("Los segundos por parte deben ser un numero entero.") from exc
            equal_parts_count = max(self._parse_positive_int(equal_parts_raw, 2), 2)

        self._persist_ui_settings()

        return SplitJobConfig(
            input_video=Path(video_raw),
            output_dir=Path(output_raw),
            split_mode=split_mode,
            segment_seconds=segment_seconds,
            equal_parts_count=equal_parts_count,
            video_profile=video_profile,
            container_format=container_format,
            processing_device=processing_device,
        )

    def _persist_ui_settings_event(self, _event: tk.Event[tk.Misc]) -> None:
        self._persist_ui_settings()

    def _persist_ui_settings(self) -> None:
        save_ui_settings(
            split_mode=self.split_mode_var.get().strip() or DEFAULT_SPLIT_MODE,
            segment_seconds=self._parse_positive_int(self.segment_var.get(), 60),
            equal_parts_count=max(self._parse_positive_int(self.equal_parts_var.get(), 2), 2),
            video_profile=self.video_profile_var.get().strip() or DEFAULT_VIDEO_PROFILE,
            container_format=self.container_format_var.get().strip() or DEFAULT_CONTAINER_FORMAT,
            processing_device=self.processing_device_var.get().strip() or DEFAULT_PROCESSING_DEVICE,
            output_dir=self.output_var.get().strip(),
        )

    def _sync_split_mode_controls(self) -> None:
        use_equal_parts = self.split_mode_var.get() == EQUAL_PARTS_SPLIT_MODE
        self.segment_entry.state(["disabled"] if use_equal_parts else ["!disabled"])
        self.equal_parts_entry.state(["!disabled"] if use_equal_parts else ["disabled"])

    @staticmethod
    def _parse_positive_int(raw_value: str, default: int) -> int:
        try:
            value = int(raw_value.strip())
        except ValueError:
            return default
        return value if value > 0 else default

    def _run_split_job(self, config: SplitJobConfig) -> None:
        try:
            service = VideoSplitterService()
            with self._service_lock:
                self._active_service = service
            files = service.split_video(config, progress_callback=self._queue_progress)
            self._events.put(("done", files))
        except SplitCancelledError as exc:
            self._events.put(("canceled", str(exc)))
        except FFmpegBinaryNotFoundError as exc:
            self._events.put(("ffmpeg_missing", str(exc)))
        except VideoSplitterError as exc:
            self._events.put(("error", str(exc)))
        except Exception as exc:  # pragma: no cover
            self._events.put(("error", f"Error inesperado: {exc}"))
        finally:
            with self._service_lock:
                self._active_service = None

    def _queue_progress(self, percent: float | None, message: str) -> None:
        self._events.put(("progress", (percent, message)))

    def _flush_events(self) -> None:
        while True:
            try:
                event, payload = self._events.get_nowait()
            except queue.Empty:
                break

            if event == "progress":
                percent, message = payload  # type: ignore[misc]
                self._update_progress(percent, message)
            elif event == "done":
                files = payload  # type: ignore[assignment]
                self._finish_with_success(files)
            elif event == "ffmpeg_missing":
                self._handle_missing_ffmpeg(str(payload))
            elif event == "canceled":
                self._finish_with_cancellation(str(payload))
            elif event == "error":
                self._finish_with_error(str(payload))

        self.root.after(self._POLL_INTERVAL_MS, self._flush_events)

    def _handle_missing_ffmpeg(self, error_message: str) -> None:
        self._stop_progress_animation()
        self._set_running_state(False)
        self.status_var.set("FFmpeg no esta configurado.")

        ask_to_select = messagebox.askyesno(
            "FFmpeg no encontrado",
            f"{error_message}\n\nQuieres seleccionar ffmpeg.exe ahora?",
            parent=self.root,
        )
        if not ask_to_select:
            return

        if not self._prompt_and_save_ffmpeg():
            return

        should_retry = messagebox.askyesno(
            "Reintentar",
            "FFmpeg fue guardado.\nDeseas reintentar la division ahora?",
            parent=self.root,
        )
        if should_retry:
            self._start_job()

    def _update_progress(self, percent: float | None, message: str) -> None:
        if percent is None:
            if not self._progress_indeterminate:
                self.progress_bar.configure(mode="indeterminate")
                self.progress_bar.start(9)
                self._progress_indeterminate = True
            self.processed_percent_var.set("Procesado: calculando...")
            self.pending_percent_var.set("Pendiente: calculando...")
        else:
            if self._progress_indeterminate:
                self.progress_bar.stop()
                self.progress_bar.configure(mode="determinate")
                self._progress_indeterminate = False
            normalized = max(0.0, min(percent, 100.0))
            self.progress_var.set(normalized)
            self.processed_percent_var.set(f"Procesado: {normalized:.1f}%")
            self.pending_percent_var.set(f"Pendiente: {max(100.0 - normalized, 0.0):.1f}%")

        self.status_var.set(message)

    def _finish_with_success(self, files: list[Path]) -> None:
        self._stop_progress_animation()
        self.progress_var.set(100.0)
        self.processed_percent_var.set("Procesado: 100.0%")
        self.pending_percent_var.set("Pendiente: 0.0%")
        self.status_var.set(
            f"Proceso completado. Archivos generados: {len(files)}. "
            f"Formato: {self._selected_format_label()}. "
            f"Procesamiento: {self._selected_processing_label()}"
        )
        self._set_running_state(False)

        messagebox.showinfo(
            "Completado",
            f"Se generaron {len(files)} parte(s) en:\n{files[0].parent if files else self.output_var.get()}",
            parent=self.root,
        )

    def _finish_with_error(self, error_message: str) -> None:
        self._stop_progress_animation()
        self._set_running_state(False)
        self.processed_percent_var.set(f"Procesado: {self.progress_var.get():.1f}%")
        self.pending_percent_var.set(f"Pendiente: {max(100.0 - self.progress_var.get(), 0.0):.1f}%")
        self.status_var.set("El proceso termino con error.")
        messagebox.showerror("Error", error_message, parent=self.root)

    def _finish_with_cancellation(self, message: str) -> None:
        self._stop_progress_animation()
        self._set_running_state(False)
        current = max(0.0, min(self.progress_var.get(), 100.0))
        self.processed_percent_var.set(f"Procesado: {current:.1f}%")
        self.pending_percent_var.set(f"Pendiente: {max(100.0 - current, 0.0):.1f}%")
        self.status_var.set("Conversion cancelada por el usuario.")
        messagebox.showinfo("Cancelado", message or "Conversion cancelada por el usuario.", parent=self.root)

    def _stop_progress_animation(self) -> None:
        if self._progress_indeterminate:
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            self._progress_indeterminate = False

    def _set_running_state(self, running: bool) -> None:
        for control in self._controls:
            if running:
                control.state(["disabled"])
            else:
                control.state(["!disabled"])

        self.start_button.configure(
            text="Procesando..." if running else "Dividir Video",
            state=("disabled" if running else "normal"),
        )
        self.cancel_button.configure(state=("normal" if running else "disabled"))

