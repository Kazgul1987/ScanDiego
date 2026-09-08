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
    NO_MATCH = "no_match"


@dataclass(slots=True, frozen=True)
class ExternalPlatform:
    external_platform_id: str
    external_platform_name: str
    normalized_platform: str


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
    available_platforms: list[ExternalPlatform] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class CoverResult:
    url: str
    kind: str = "poster"
    width: int | None = None
    height: int | None = None
    external_game_id: str | None = None


@dataclass(slots=True, frozen=True)
class ArtworkCandidate:
    """A stable, provider-neutral artwork choice shown to the user."""
    artwork_id: str
    external_game_id: str
    game_title: str
    image_url: str
    thumb_url: str | None = None
    width: int | None = None
    height: int | None = None
    score: float = 0.0
    style: str | None = None
    tags: tuple[str, ...] = ()


@dataclass(slots=True)
class ProviderHealthResult:
    success: bool
    status: str
    message: str
    latency_ms: float | None = None
