from __future__ import annotations

import re
from pathlib import Path


def clean_title_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    title = stem.replace("_", " ")
    title = re.sub(r"\s+", " ", title).strip()
    return title


def human_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size_bytes)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{size_bytes} B"
