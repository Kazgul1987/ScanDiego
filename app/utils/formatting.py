from __future__ import annotations

from app.services.title_normalization_service import TitleNormalizationService


def clean_title_from_filename(filename: str) -> str:
    """Compatibility wrapper for callers of the original helper."""
    return TitleNormalizationService().normalize(filename)


def human_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size_bytes)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{size_bytes} B"
