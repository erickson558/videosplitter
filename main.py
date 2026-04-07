"""Application entrypoint for Video Splitter desktop app."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

from app_metadata import APP_TITLE
from frontend.main_window import VideoSplitterApp, create_root_window


def _runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _first_icon(directory: Path) -> Path | None:
    icons = sorted(directory.glob("*.ico"))
    return icons[0] if icons else None


def main() -> None:
    root = create_root_window()
    root.title(APP_TITLE)

    icon = _first_icon(_runtime_dir())
    if icon:
        try:
            root.iconbitmap(default=str(icon))
        except tk.TclError:
            pass

    VideoSplitterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

