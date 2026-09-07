from __future__ import annotations

import logging
import re
from pathlib import Path

from app.models.content import ContentDetectionMethod, ContentDetectionResult, MediaContentType
from app.services.base_title_detection_service import BaseTitleDetectionService
from app.services.switch_content_detection_service import SwitchContentDetectionService
from app.services.version_detection_service import VersionDetectionService

LOGGER = logging.getLogger(__name__)


class ContentDetectionService:
    _UPDATE = re.compile(r"\b(?:title\s+update|update|patch|version|ver)\b|(?:^|[\s._-])v\d+(?:\.\d+)+\b", re.I)
    _DLC = re.compile(r"\b(?:dlc|add-?on|expansion|season\s+pass|fighter\s+pass|costume\s+pack|character\s+pack|bonus\s+content|expansion\s+pass|story\s+expansion)\b", re.I)
    _DEMO = re.compile(r"\b(?:demo|trial|prototype|beta)\b", re.I)

    def __init__(self, parsers=None) -> None:
        self.parsers = list(parsers or [SwitchContentDetectionService()])
        self.versions = VersionDetectionService()
        self.base_titles = BaseTitleDetectionService()

    def detect(self, path: str | Path) -> ContentDetectionResult:
        path = Path(path)
        LOGGER.info("Content-Erkennung gestartet: %s", path)
        warnings: list[str] = []
        for parser in self.parsers:
            result = parser.parse(path)
            if not result.supported:
                continue
            warnings.extend(result.warnings)
            if result.readable and result.content_type is not MediaContentType.UNKNOWN:
                LOGGER.info("Container-Metadaten gelesen; Content-Typ erkannt: %s", result.content_type)
                return ContentDetectionResult(result.content_type, result.title, result.version,
                    result.content_id, result.base_content_id, result.region, result.confidence,
                    ContentDetectionMethod.CONTAINER_METADATA, tuple(warnings))
            LOGGER.warning("Container metadata unavailable für %s; Fallback auf Filename", path)
        stem = path.stem.replace("_", " ").strip()
        title_id_match = re.search(r"\[([0-9A-F]{16})\]", stem, re.I)
        if title_id_match:
            content_id = title_id_match.group(1).upper()
            content_type, base_id = SwitchContentDetectionService.classify_title_id(content_id)
            clean_stem = (stem[:title_id_match.start()] + stem[title_id_match.end():]).strip()
            title = self.base_titles.derive(clean_stem, content_type)
            LOGGER.info("Content-Typ über Switch Title-ID erkannt: %s", content_type)
            return ContentDetectionResult(content_type, title, self.versions.detect(stem), content_id,
                                          base_id, confidence=.95,
                                          method=ContentDetectionMethod.TECHNICAL_ID,
                                          warnings=tuple(warnings))
        content_type = MediaContentType.BASE_GAME
        confidence = .65
        if self._DEMO.search(stem): content_type, confidence = MediaContentType.DEMO, .9
        elif self._DLC.search(stem): content_type, confidence = MediaContentType.DLC, .86
        elif self._UPDATE.search(stem): content_type, confidence = MediaContentType.UPDATE, .9
        title = self.base_titles.derive(stem, content_type)
        method = ContentDetectionMethod.FILENAME
        LOGGER.info("Content-Typ erkannt: %s (%s)", content_type, method)
        return ContentDetectionResult(content_type, title, self.versions.detect(stem),
                                      confidence=confidence, method=method, warnings=tuple(warnings))
