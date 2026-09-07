from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.models.content import ContentDetectionResult, MediaContentType
from app.services.title_normalization_service import TitleNormalizationService

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ContentAssociationResult:
    parent_game_id: int | None
    confidence: float
    reason: str
    ambiguous: bool = False


class ContentAssociationService:
    def __init__(self) -> None:
        self.titles = TitleNormalizationService()

    def associate(self, detection: ContentDetectionResult, platform: str,
                  games: Sequence[Mapping[str, Any]], current: Mapping[str, Any] | None = None
                  ) -> ContentAssociationResult:
        if current and current.get("content_locked"):
            LOGGER.info("Content-Lock respektiert: media=%s", current.get("id"))
            return ContentAssociationResult(current.get("content_parent_game_id") or current.get("game_id"), 1.0, "manual")
        candidates = [g for g in games if str(g.get("platform", "Unknown")) == platform]
        technical = []
        if detection.base_content_id:
            wanted = detection.base_content_id.casefold()
            technical = [g for g in candidates if str(g.get("base_content_id") or g.get("content_id") or "").casefold() == wanted]
        if len(technical) == 1:
            LOGGER.info("Parent-Game gefunden (technische ID): %s", technical[0]["id"])
            return ContentAssociationResult(int(technical[0]["id"]), .99, "technical_id")
        title = self.titles.normalize(detection.title or "").casefold()
        by_title = [g for g in candidates if self.titles.normalize(str(g.get("title", ""))).casefold() == title]
        # Prefer candidates with a known base file. This also prevents attachment
        # to an old standalone DLC record with the same derived title.
        with_base = [g for g in by_title if g.get("has_base", True)]
        by_title = with_base or by_title
        if len(by_title) == 1:
            LOGGER.info("Parent-Game gefunden (Titel/Plattform): %s", by_title[0]["id"])
            return ContentAssociationResult(int(by_title[0]["id"]), .9, "title_platform")
        if len(technical) > 1 or len(by_title) > 1:
            LOGGER.warning("Parent unsicher: %s", detection.title)
            return ContentAssociationResult(None, 0.0, "ambiguous", True)
        if detection.content_type in {MediaContentType.DLC, MediaContentType.ADDON}:
            LOGGER.warning("DLC ohne Parent: %s", detection.title)
        elif detection.content_type is MediaContentType.UPDATE:
            LOGGER.warning("Update ohne Parent: %s", detection.title)
        return ContentAssociationResult(None, 0.0, "not_found")
