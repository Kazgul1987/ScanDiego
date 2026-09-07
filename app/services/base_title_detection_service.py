from __future__ import annotations

import re

from app.models.content import MediaContentType


class BaseTitleDetectionService:
    """Removes only explicit content suffixes; normal title normalization stays untouched."""

    _UPDATE = re.compile(r"(?:\s*[-–—:]\s*|\s+)(?:title\s+)?(?:update|patch|version|ver)\b.*$", re.I)
    _DEMO = re.compile(r"(?:\s*[-–—:]\s*|\s+)(?:demo|trial|prototype|beta)\b.*$", re.I)
    _PACK = re.compile(r"\b(?:expansion(?:\s+pass)?|season\s+pass|fighter\s+pass|costume\s+pack|character\s+pack|bonus\s+content|story\s+expansion)\b.*$", re.I)
    _DLC = re.compile(r"(?:\s*[-–—:]\s*|\s+)(?:\S+\s+)?(?:dlc|add-?on)\b.*$", re.I)

    def derive(self, title: str, content_type: MediaContentType) -> str | None:
        pattern = {
            MediaContentType.UPDATE: self._UPDATE,
            MediaContentType.DEMO: self._DEMO,
            MediaContentType.DLC: self._PACK,
            MediaContentType.ADDON: self._PACK,
        }.get(content_type)
        candidate = (pattern.sub("", title) if pattern else title).strip(" ._-–—:[]()")
        # Named expansion/DLC suffixes commonly contain one product name directly
        # before the marker ("Seasons Expansion", "Joker DLC"). Remove that name
        # only when at least a substantial base title remains.
        if (content_type in {MediaContentType.DLC, MediaContentType.ADDON} and
                pattern is self._PACK and self._PACK.search(title)):
            words = candidate.split()
            if len(words) >= 4:
                candidate = " ".join(words[:-1])
        if content_type in {MediaContentType.DLC, MediaContentType.ADDON} and candidate == title.strip(" ._-–—:[]()"):
            marker = re.search(r"\b(?:dlc|add-?on)\b", title, re.I)
            prefix = title[:marker.start()].strip() if marker else title
            separated = re.split(r"\s+[-–—:]\s+", prefix)
            if len(separated) > 1:
                candidate = separated[0]
            else:
                words = prefix.split()
                candidate = " ".join(words[:-1]) if len(words) >= 4 else prefix
            candidate = candidate.strip(" ._-–—:[]()")
        return candidate or None
