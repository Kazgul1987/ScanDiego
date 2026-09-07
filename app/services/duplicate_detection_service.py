from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Any

LOGGER = logging.getLogger(__name__)


class DuplicateStatus(StrEnum):
    NONE = "none"
    POSSIBLE = "possible"
    PROBABLE = "probable"
    CONFIRMED = "confirmed"


@dataclass(frozen=True, slots=True)
class DuplicateGroup:
    status: DuplicateStatus
    normalized_title: str
    platform: str
    entries: tuple[Mapping[str, Any], ...]


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

    def groups(self, entries: list[Mapping[str, Any]]) -> list[DuplicateGroup]:
        """Classify groups once for use by persistence, counts and UI.

        Confirmed groups take precedence. Probable size-groups and possible
        title/platform groups may overlap because both are useful findings.
        """
        available = [entry for entry in entries if not entry.get("is_missing")]
        result: list[DuplicateGroup] = []
        confirmed_ids: set[int] = set()
        hash_buckets: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
        for entry in available:
            digest, hash_type = entry.get("file_hash"), entry.get("hash_type")
            if digest and hash_type:
                hash_buckets.setdefault((str(hash_type).casefold(), str(digest)), []).append(entry)
        for bucket in hash_buckets.values():
            if len(bucket) > 1:
                confirmed_ids.update(id(entry) for entry in bucket)
                titles = {str(entry.get("title", "")) for entry in bucket}
                platforms = {str(entry.get("platform", "Unknown")) for entry in bucket}
                result.append(DuplicateGroup(DuplicateStatus.CONFIRMED,
                    titles.pop() if len(titles) == 1 else "Verschiedene Titel",
                    platforms.pop() if len(platforms) == 1 else "Verschiedene Plattformen", tuple(bucket)))

        title_buckets: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
        for entry in available:
            if id(entry) not in confirmed_ids:
                key = (str(entry.get("title", "")).casefold(), str(entry.get("platform", "Unknown")))
                title_buckets.setdefault(key, []).append(entry)
        for bucket in title_buckets.values():
            if len(bucket) < 2:
                continue
            sizes: dict[int, list[Mapping[str, Any]]] = {}
            for entry in bucket:
                sizes.setdefault(int(entry.get("file_size", 0)), []).append(entry)
            for same_size in sizes.values():
                if len(same_size) > 1:
                    result.append(DuplicateGroup(DuplicateStatus.PROBABLE,
                        str(same_size[0].get("title", "")), str(same_size[0].get("platform", "Unknown")), tuple(same_size)))
            if len(sizes) > 1:
                result.append(DuplicateGroup(DuplicateStatus.POSSIBLE,
                    str(bucket[0].get("title", "")), str(bucket[0].get("platform", "Unknown")), tuple(bucket)))
        return result
