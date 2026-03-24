from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MediaEntry:
    id: int | None
    category: str
    title: str
    original_filename: str
    full_path: str
    file_name: str
    file_extension: str
    file_size: int
    modified_time: str
    drive_letter: str
    drive_label: str
    drive_id: str
    scan_date: str
    last_seen_date: str
    is_missing: int
