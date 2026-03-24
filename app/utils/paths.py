from __future__ import annotations

from pathlib import Path
import sys


def get_base_dir() -> Path:
    """Return the portable runtime base directory."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def get_data_dir() -> Path:
    return get_base_dir() / "data"


def get_logs_dir() -> Path:
    return get_base_dir() / "logs"


def get_database_path() -> Path:
    return get_data_dir() / "scandiego.db"


def ensure_runtime_dirs() -> None:
    get_data_dir().mkdir(parents=True, exist_ok=True)
    get_logs_dir().mkdir(parents=True, exist_ok=True)
