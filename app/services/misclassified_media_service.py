from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path, PurePath, PureWindowsPath
from typing import Any, Iterable

from app.services.media_validation_service import MediaValidationService


SAFE_REASONS = frozenset({
    "rejected_switch_cartridge_metadata", "rejected_ps3_internal_file",
    "rejected_shader_cso", "rejected_markdown_file", "rejected_emulator_cache",
    "rejected_cue_companion_bin", "rejected_internal_binary",
    "rejected_non_game_disk_image",
})
LIKELY_REASONS = frozenset({"rejected_pc_game_internal_binary"})
REVIEW_REASONS = frozenset({"ambiguous_insufficient_context"})


def safety_level(reason: str, confidence: float, scan_root: str | None) -> str:
    """Apply the one conservative policy used by both cleanup data and UI."""
    if scan_root and reason in SAFE_REASONS and confidence >= .95:
        return "safe"
    if scan_root and reason in LIKELY_REASONS and confidence >= .85:
        return "likely"
    return "review"


@dataclass(frozen=True)
class MisclassifiedMediaCandidate:
    media_file_id: int
    game_id: int
    title: str
    platform: str
    full_path: str
    file_name: str
    reason: str
    confidence: float
    scan_root: str | None
    safety_level: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def infer_scan_root(full_path: str) -> str | None:
    """Recover an exact `<drive>/Games|ROMs` ancestor without substring matching."""
    path: PurePath = PureWindowsPath(full_path) if "\\" in full_path else Path(full_path)
    for index, part in enumerate(path.parts[:-1]):
        if part.casefold() in {"games", "roms"}:
            # A root name occurring deeper in an arbitrary tree is not authoritative.
            if isinstance(path, PureWindowsPath) and index == 1 and path.drive:
                return str(PureWindowsPath(*path.parts[:index + 1]))
            if not isinstance(path, PureWindowsPath) and path.is_absolute():
                return str(Path(*path.parts[:index + 1]))
    return None


def classify_candidate(row: dict[str, Any], siblings: Iterable[str | Path],
                       scan_root: str | None = None) -> MisclassifiedMediaCandidate | None:
    root = scan_root or infer_scan_root(str(row["full_path"]))
    result = MediaValidationService.classify(
        row["full_path"], scan_root=root, detected_platform=row.get("platform"),
        sibling_files=siblings)
    if result.is_media:
        return None
    return MisclassifiedMediaCandidate(
        int(row["media_file_id"]), int(row["game_id"]), str(row.get("title", "")),
        str(row.get("platform", "")), str(row["full_path"]), str(row.get("file_name", "")),
        result.reason, result.confidence, root,
        safety_level(result.reason, result.confidence, root))
