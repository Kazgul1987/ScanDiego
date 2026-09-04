from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

LOGGER = logging.getLogger(__name__)


class HashingWorker(QObject):
    completed = Signal(int, str, str)
    failed = Signal(int, str)
    progress = Signal(int)

    def __init__(self, media_file_id: int, path: str, chunk_size: int = 4 * 1024 * 1024) -> None:
        super().__init__()
        self.media_file_id = media_file_id
        self.path = Path(path)
        self.chunk_size = chunk_size

    @Slot()
    def run(self) -> None:
        LOGGER.info("SHA-256 gestartet: %s", self.path)
        digest = hashlib.sha256()
        try:
            total = self.path.stat().st_size
            read = 0
            with self.path.open("rb") as stream:
                while chunk := stream.read(self.chunk_size):
                    digest.update(chunk)
                    read += len(chunk)
                    self.progress.emit(int(read * 100 / total) if total else 100)
            self.completed.emit(self.media_file_id, digest.hexdigest(), "sha256")
            LOGGER.info("SHA-256 abgeschlossen: %s", self.path)
        except OSError as exc:
            LOGGER.exception("Hashing fehlgeschlagen: %s", self.path)
            self.failed.emit(self.media_file_id, str(exc))
