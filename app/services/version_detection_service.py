from __future__ import annotations

import re


class VersionDetectionService:
    _PATTERNS = (
        re.compile(r"\[(?:v|ver(?:sion)?)\s*(\d+)\]", re.I),
        re.compile(r"\b(?:update|patch|version|ver)\s*[._-]?\s*v?(\d+(?:\.\d+)+)\b", re.I),
        re.compile(r"(?:^|[\s._\-\[])v(\d+(?:\.\d+)+)(?=$|[\s._\-\]])", re.I),
    )

    def detect(self, value: str) -> str | None:
        for pattern in self._PATTERNS:
            match = pattern.search(value)
            if match:
                return match.group(1)
        return None
