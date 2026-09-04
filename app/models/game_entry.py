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
    platform: str = "Unknown"
    platform_overridden: int = 0
    file_hash: str | None = None
    hash_type: str | None = None
    hash_calculated_at: str | None = None
