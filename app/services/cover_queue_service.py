from __future__ import annotations
import logging, threading, time
from app.models.metadata import ExternalGame

LOGGER = logging.getLogger(__name__)

class CoverQueueService:
    """Artwork-only queue; it deliberately never writes metadata columns."""
    def __init__(self, db, artwork, interval=.3):
        self.db, self.artwork, self.interval = db, artwork, interval
        self._cancel = threading.Event(); self._pause = threading.Event()
    def pause(self): self._pause.set()
    def resume(self): self._pause.clear()
    def cancel(self): self._cancel.set()
    def process(self, progress=None):
        stats = {"processed": 0, "covered": 0, "ambiguous": 0, "failed": 0}
        rows = self.db.queued_covers(); total = len(rows)
        for row in rows:
            if self._cancel.is_set(): break
            while self._pause.is_set() and not self._cancel.wait(.1): pass
            if self._cancel.is_set(): break
            try:
                LOGGER.info('Artwork search game_id=%s title="%s" platform="%s" year=%s', row["id"],
                            row["canonical_title"] or row["title"], row["platform"], row["release_year"])
                self.db.set_artwork_result(row["id"], "searching")
                game = ExternalGame(row["external_game_id"], row["canonical_title"] or row["title"], row["platform"],
                                    release_date=row["release_date"], release_year=row["release_year"])
                old_path = row["cover_path"]
                result = self.artwork.fetch_with_match(row["id"], game, force=bool(row["artwork_force_refresh"]),
                                                       artwork_external_id=row["artwork_external_game_id"])
                if result:
                    path, artwork_id = result
                    self.db.set_artwork_result(row["id"], "matched", str(path), self.artwork.provider.name, artwork_id); stats["covered"] += 1
                    if old_path and old_path != str(path) and not self.db.cover_path_is_shared(old_path, row["id"]):
                        self.artwork.remove(old_path)
                else:
                    status = getattr(self.artwork.provider, "last_search_status", "ambiguous")
                    self.db.set_artwork_result(row["id"], status)
                    if status == "ambiguous": stats["ambiguous"] += 1
            except Exception:
                LOGGER.exception("Artwork download failed game_id=%s", row["id"])
                self.db.set_artwork_result(row["id"], "failed"); stats["failed"] += 1
            stats["processed"] += 1
            if progress: progress(stats["processed"], total, stats["covered"], stats["ambiguous"], stats["failed"])
            if self._cancel.wait(self.interval): break
        return stats
