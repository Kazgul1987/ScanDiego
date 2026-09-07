from __future__ import annotations
from PySide6.QtCore import QObject, Signal, Slot
from app.database.db_manager import DatabaseManager
from app.providers.igdb import IGDBProvider
from app.providers.steamgriddb import SteamGridDBProvider
from app.services.artwork_service import ArtworkService
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
            provider = IGDBProvider(self.settings.igdb_client_id, self.settings.igdb_client_secret)
            artwork = None
            if self.settings.automatic_covers:
                artwork = ArtworkService(SteamGridDBProvider(self.settings.steamgriddb_api_key))
            self.queue = MetadataQueueService(db, provider, GameMatchingService(self.settings.automatic_threshold, self.settings.ambiguous_threshold), artwork, self.settings.request_interval)
            self.finished.emit(self.queue.process())
        except Exception as exc: self.failed.emit(str(exc))
        finally: db.close()
    def cancel(self):
        if self.queue: self.queue.cancel()
