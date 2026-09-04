from __future__ import annotations

import logging
from enum import StrEnum
from typing import Mapping, Any

LOGGER = logging.getLogger(__name__)


class DuplicateStatus(StrEnum):
    NONE = "none"
    POSSIBLE = "possible"
    PROBABLE = "probable"
    CONFIRMED = "confirmed"


class DuplicateDetectionService:
    def compare(self, left: Mapping[str, Any], right: Mapping[str, Any]) -> DuplicateStatus:
        left_hash, right_hash = left.get("file_hash"), right.get("file_hash")
        if left_hash and right_hash and left_hash == right_hash and left.get("hash_type") == right.get("hash_type"):
            return DuplicateStatus.CONFIRMED
        same_title = str(left.get("title", "")).casefold() == str(right.get("title", "")).casefold()
        same_platform = left.get("platform") == right.get("platform")
        if not (same_title and same_platform):
            return DuplicateStatus.NONE
        if left.get("file_size") == right.get("file_size"):
            return DuplicateStatus.PROBABLE
        LOGGER.debug("Possible duplicate: %s / %s", left.get("title"), right.get("title"))
        return DuplicateStatus.POSSIBLE

