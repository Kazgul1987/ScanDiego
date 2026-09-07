from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class MediaContentType(StrEnum):
    BASE_GAME = "base_game"
    UPDATE = "update"
    DLC = "dlc"
    ADDON = "addon"
    DEMO = "demo"
    UNKNOWN = "unknown"


class ContentDetectionMethod(StrEnum):
    CONTAINER_METADATA = "container_metadata"
    TECHNICAL_ID = "technical_id"
    FILENAME = "filename"
    PATH = "path"
    MANUAL = "manual"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ContentDetectionResult:
    content_type: MediaContentType = MediaContentType.UNKNOWN
    title: str | None = None
    version: str | None = None
    content_id: str | None = None
    base_content_id: str | None = None
    region: str | None = None
    confidence: float = 0.0
    method: ContentDetectionMethod = ContentDetectionMethod.UNKNOWN
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ContentParserResult:
    supported: bool
    readable: bool
    content_type: MediaContentType = MediaContentType.UNKNOWN
    content_id: str | None = None
    base_content_id: str | None = None
    title: str | None = None
    version: str | None = None
    region: str | None = None
    confidence: float = 0.0
    warnings: tuple[str, ...] = field(default_factory=tuple)
