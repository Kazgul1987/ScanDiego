from __future__ import annotations
from PySide6.QtCore import QObject, Signal, Slot
from app.database.db_manager import DatabaseManager
from app.providers.factory import create_metadata_provider
from app.services.game_matching_service import GameMatchingService
from app.services.metadata_queue_service import MetadataQueueService
from app.settings import MetadataSettings


class MetadataWorker(QObject):
    finished = Signal(dict)
    failed = Signal(str)
    def __init__(self, db_path, settings: MetadataSettings): super().__init__(); self.db_path, self.settings = db_path, settings; self.queue = None
    @Slot()
    def run(self):
        db = DatabaseManager(self.db_path)
        try:
            provider = create_metadata_provider(self.settings)
            self.queue = MetadataQueueService(db, provider, GameMatchingService(self.settings.automatic_threshold, self.settings.ambiguous_threshold), interval=self.settings.request_interval)
            self.finished.emit(self.queue.process())
        except Exception as exc: self.failed.emit(str(exc))
        finally: db.close()
    def cancel(self):
        if self.queue: self.queue.cancel()
    def pause(self):
        if self.queue: self.queue.pause()
    def resume(self):
        if self.queue: self.queue.resume()
