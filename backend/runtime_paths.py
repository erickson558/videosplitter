"""Runtime path utilities shared across backend modules."""

from __future__ import annotations

import sys
from pathlib import Path


def runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def bundle_root() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None

    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return None

    return Path(meipass).resolve()
