from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.models.content import ContentParserResult


class ContentMetadataParser(ABC):
    """Bounded, non-DRM parser contract for replaceable platform parsers."""

    @abstractmethod
    def parse(self, path: Path) -> ContentParserResult:
        raise NotImplementedError
