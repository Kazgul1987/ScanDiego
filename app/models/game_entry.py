from __future__ import annotations

from dataclasses import dataclass

from app.models.content import ContentDetectionMethod, MediaContentType


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
    content_type: str = MediaContentType.UNKNOWN
    content_title: str | None = None
    content_version: str | None = None
    content_id: str | None = None
    base_content_id: str | None = None
    content_detection_method: str = ContentDetectionMethod.UNKNOWN
    content_detection_confidence: float = 0.0
    content_parent_game_id: int | None = None
    content_region: str | None = None
    content_locked: int = 0
