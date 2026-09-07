from __future__ import annotations
import logging, threading, time
from dataclasses import replace
from app.models.metadata import ExternalPlatform, MetadataStatus
from app.providers.base import MetadataProvider
from app.services.game_matching_service import GameMatchingService
from app.services.metadata_completeness_service import MetadataCompletenessService
from app.services.platform_detection_service import PlatformDetectionService

LOGGER = logging.getLogger(__name__)


class MetadataQueueService:
    """Persistent, sequential queue processor. Run ``process`` in a QThread/worker."""
    def __init__(self, db, provider: MetadataProvider, matcher: GameMatchingService, artwork=None, interval=.3):
        self.db, self.provider, self.matcher, self.artwork, self.interval = db, provider, matcher, artwork, interval
        self._cancel = threading.Event(); self._pause = threading.Event()

    def enqueue(self, game_ids=None, force=False) -> int: return self.db.enqueue_metadata(game_ids, force)
    def pause(self): self._pause.set()
    def resume(self): self._pause.clear()
    def cancel(self): self._cancel.set()

    def process(self) -> dict[str, int]:
        stats = {"processed": 0, "matched": 0, "ambiguous": 0, "failed": 0}
        LOGGER.info("Metadata Queue gestartet")
        for local in self.db.queued_games():
            if self._cancel.is_set(): break
            while self._pause.is_set() and not self._cancel.wait(.1): pass
            if self._cancel.is_set(): break
            game_id = local["id"]
            try:
                if local["metadata_locked"] and not local["external_game_id"]:
                    continue
                self.db.set_metadata_status(game_id, MetadataStatus.SEARCHING)
                if local["external_game_id"] and local["metadata_source"] == self.provider.name:
                    external = self.provider.get_game(local["external_game_id"]); score = local["metadata_match_score"] or 100
                    selected = next((p for p in external.available_platforms
                                     if p.normalized_platform == PlatformDetectionService.family(local["platform"])), None)
                    if selected:
                        external = replace(external, platform=local["platform"],
                                           external_platform_id=selected.external_platform_id)
                    state = MetadataCompletenessService.status(external)
                    self.db.apply_metadata(game_id, external, self.provider.name, score, "refresh", MetadataStatus(state))
                else:
                    ranked = self.matcher.rank(local["title"], local["platform"], self.provider.search_game(local["title"], local["platform"]), local["release_year"])
                    state = self.matcher.classify(ranked)
                    self.db.save_candidates(game_id, self.provider.name, ranked)
                    if state == "matched":
                        external = ranked[0].game
                        choices = [p for p in external.available_platforms if p.normalized_platform != "Unknown"]
                        if not choices and external.platform:
                            choices = [ExternalPlatform(external.external_platform_id or "", external.platform,
                                                       PlatformDetectionService.family(external.platform))]
                        local_platform = local["platform"]
                        if local_platform == "Unknown" and len(choices) != 1:
                            state = "ambiguous"
                            self.db.set_metadata_status(game_id, MetadataStatus.AMBIGUOUS)
                            external = None
                        else:
                            selected = (next((p for p in choices if p.normalized_platform == PlatformDetectionService.family(local_platform)), None)
                                        if local_platform != "Unknown" else choices[0] if choices else None)
                            if selected:
                                external = replace(external, platform=selected.normalized_platform,
                                                   external_platform_id=selected.external_platform_id)
                            state = MetadataCompletenessService.status(external)
                            self.db.apply_metadata(game_id, external, self.provider.name, ranked[0].score,
                                                   "automatic", MetadataStatus(state), local_platform == "Unknown")
                    else: self.db.set_metadata_status(game_id, MetadataStatus(state)); external = None
                stats["matched" if state == "incomplete" else state] += 1
                # Compatibility for automatic-cover callers: dispatch through the
                # independent artwork queue, never through metadata persistence.
                if external and self.artwork:
                    from app.services.cover_queue_service import CoverQueueService
                    self.db.enqueue_covers([game_id])
                    CoverQueueService(self.db, self.artwork, 0).process()
                LOGGER.info("Metadata Match game=%s status=%s", game_id, state)
            except Exception as exc:
                LOGGER.warning("Provider-Fehler für Game %s: %s", game_id, exc)
                self.db.set_metadata_status(game_id, MetadataStatus.FAILED); stats["failed"] += 1
            stats["processed"] += 1; time.sleep(self.interval)
        LOGGER.info("Metadata Queue beendet: %s", stats)
        return stats
