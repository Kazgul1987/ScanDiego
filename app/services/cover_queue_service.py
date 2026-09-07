from __future__ import annotations
import threading, time
from app.models.metadata import ExternalGame

class CoverQueueService:
    """Artwork-only queue; it deliberately never writes metadata columns."""
    def __init__(self, db, artwork, interval=.3):
        self.db, self.artwork, self.interval = db, artwork, interval
        self._cancel = threading.Event(); self._pause = threading.Event()
    def pause(self): self._pause.set()
    def resume(self): self._pause.clear()
    def cancel(self): self._cancel.set()
    def process(self):
        stats = {"processed": 0, "covered": 0, "ambiguous": 0, "failed": 0}
        for row in self.db.queued_covers():
            if self._cancel.is_set(): break
            while self._pause.is_set() and not self._cancel.wait(.1): pass
            try:
                self.db.set_artwork_result(row["id"], "searching")
                game = ExternalGame(row["external_game_id"], row["canonical_title"] or row["title"], row["platform"],
                                    release_date=row["release_date"], release_year=row["release_year"])
                result = self.artwork.fetch_with_match(row["id"], game, artwork_external_id=row["artwork_external_game_id"])
                if result:
                    path, artwork_id = result
                    self.db.set_artwork_result(row["id"], "matched", str(path), self.artwork.provider.name, artwork_id); stats["covered"] += 1
                else: self.db.set_artwork_result(row["id"], "ambiguous"); stats["ambiguous"] += 1
            except Exception:
                self.db.set_artwork_result(row["id"], "failed"); stats["failed"] += 1
            stats["processed"] += 1; time.sleep(self.interval)
        return stats
