from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class MetadataStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    QUEUED = "queued"
    SEARCHING = "searching"
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    INCOMPLETE = "incomplete"
    FAILED = "failed"
    MANUAL = "manual"


@dataclass(slots=True)
class ExternalGame:
    external_id: str
    title: str
    platform: str = ""
    external_platform_id: str | None = None
    release_date: str | None = None
    release_year: int | None = None
    publisher: str | None = None
    developer: str | None = None
    description: str | None = None
    region: str | None = None
    payload: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class CoverResult:
    url: str
    kind: str = "poster"
    width: int | None = None
    height: int | None = None
