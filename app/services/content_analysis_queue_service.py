from __future__ import annotations

import logging
import threading

from app.models.content import MediaContentType
from app.services.content_detection_service import ContentDetectionService

LOGGER = logging.getLogger(__name__)


class ContentAnalysisQueueService:
    """Cancellable resilient post-scan analysis; callers may run it in a QThread."""

    def __init__(self, db, detector: ContentDetectionService | None = None) -> None:
        self.db = db
        self.detector = detector or ContentDetectionService()
        self._cancel = threading.Event()
        self._pause = threading.Event()

    def cancel(self) -> None: self._cancel.set()
    def pause(self) -> None: self._pause.set()
    def resume(self) -> None: self._pause.clear()

    def process(self, force: bool = False, progress=None) -> dict[str, int]:
        rows = self.db.content_analysis_candidates(force)
        stats = {"processed": 0, "updated": 0, "failed": 0}
        for index, row in enumerate(rows, 1):
            if self._cancel.is_set(): break
            while self._pause.is_set() and not self._cancel.wait(.1): pass
            try:
                result = self.detector.detect(row["full_path"])
                self.db.apply_content_detection(row["id"], result)
                stats["updated"] += 1
            except Exception as exc:  # per-file isolation is the queue boundary
                LOGGER.warning("Content-Analyse fehlgeschlagen für %s: %s", row["full_path"], exc)
                stats["failed"] += 1
            stats["processed"] += 1
            if progress: progress(index, len(rows), row["full_path"])
        return stats
