from PySide6.QtCore import QObject, Signal, Slot
from app.database.db_manager import DatabaseManager
from app.providers.factory import create_artwork_provider
from app.services.artwork_service import ArtworkService
from app.services.cover_queue_service import CoverQueueService

class CoverWorker(QObject):
    finished=Signal(dict); failed=Signal(str)
    def __init__(self, db_path, settings): super().__init__(); self.db_path=db_path; self.settings=settings; self.queue=None
    @Slot()
    def run(self):
        db=DatabaseManager(self.db_path)
        try:
            self.queue=CoverQueueService(db, ArtworkService(create_artwork_provider(self.settings)), self.settings.request_interval)
            self.finished.emit(self.queue.process())
        except Exception as exc: self.failed.emit(str(exc))
        finally: db.close()
    def cancel(self):
        if self.queue: self.queue.cancel()
