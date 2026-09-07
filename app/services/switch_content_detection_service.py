from __future__ import annotations

import json
import logging
from pathlib import Path

from app.models.content import ContentParserResult, MediaContentType
from app.services.content_metadata_parser import ContentMetadataParser

LOGGER = logging.getLogger(__name__)
SWITCH_EXTENSIONS = {".nsp", ".xci", ".nsz", ".xcz"}
FIXTURE_MAGIC = b"SCANDIEGO_CONTENT\0"
MAX_HEADER_BYTES = 64 * 1024


class SwitchContentDetectionService(ContentMetadataParser):
    """Reads only clear, bounded metadata; it never decrypts an NCA or handles keys.

    The compact magic record is intentionally public and used by synthetic tests and
    future legal exporter integrations. Normal encrypted containers return unreadable.
    """

    @staticmethod
    def classify_title_id(title_id: str) -> tuple[MediaContentType, str | None]:
        try:
            value = int(title_id, 16)
        except (TypeError, ValueError):
            return MediaContentType.UNKNOWN, None
        suffix = value & 0xFFF
        if suffix == 0:
            return MediaContentType.BASE_GAME, f"{value:016X}"
        if suffix == 0x800:
            return MediaContentType.UPDATE, f"{value - 0x800:016X}"
        # Add-on content occupies the following 0x1000 block and uses a
        # non-zero content index (for example base E000 -> DLC F001).
        base = (value & ~0xFFF) - 0x1000
        return MediaContentType.DLC, f"{base:016X}" if base >= 0 else None

    def parse(self, path: Path) -> ContentParserResult:
        if path.suffix.lower() not in SWITCH_EXTENSIONS:
            return ContentParserResult(False, False)
        try:
            with path.open("rb") as stream:
                header = stream.read(MAX_HEADER_BYTES)
        except OSError as exc:
            LOGGER.warning("Switch-Parserfehler für %s: %s", path, exc)
            return ContentParserResult(True, False, warnings=("container metadata unavailable",))
        offset = header.find(FIXTURE_MAGIC)
        if offset < 0:
            return ContentParserResult(True, False, warnings=("container metadata unavailable; encrypted or unsupported",))
        try:
            payload = json.loads(header[offset + len(FIXTURE_MAGIC):].split(b"\0", 1)[0].decode("utf-8"))
            content_id = str(payload["title_id"]).upper()
            content_type, inferred_base = self.classify_title_id(content_id)
            explicit = payload.get("content_type")
            if explicit:
                content_type = MediaContentType(explicit)
            return ContentParserResult(True, True, content_type, content_id,
                str(payload.get("base_title_id") or inferred_base).upper(), payload.get("title"),
                payload.get("version"), payload.get("region"), .98)
        except (KeyError, ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            LOGGER.warning("Switch-Parserfehler für %s: %s", path, exc)
            return ContentParserResult(True, False, warnings=("invalid clear container metadata",))
