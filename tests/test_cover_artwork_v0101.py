import threading
import time
from pathlib import Path

import pytest

from app.models.metadata import ArtworkCandidate, CoverResult, ExternalGame
from app.providers.fake import FakeArtworkProvider
from app.services.artwork_service import ArtworkService, InvalidArtworkError
from app.services.cover_queue_service import CoverQueueService


PNG = b"\x89PNG\r\n\x1a\nvalid"


class CandidateProvider(FakeArtworkProvider):
    def __init__(self):
        super().__init__(PNG); self.search_calls = 0

    def search_cover(self, game):
        self.search_calls += 1
        return [CoverResult("fake://new", external_game_id="new-game")]

    def search_artwork_candidates(self, game, limit=10):
        return [
            ArtworkCandidate("100", "10", "007 First Light", "fake://a", score=96),
            ArtworkCandidate("200", "20", "007 First Light Deluxe Edition", "fake://b", score=93),
        ][:limit]


def test_candidates_are_stable_and_manual_selection_uses_artwork(tmp_path):
    provider = CandidateProvider(); service = ArtworkService(provider, tmp_path / "covers")
    candidates = provider.search_artwork_candidates(ExternalGame("", "007 First Light", "PC", release_year=2026))
    assert [candidate.artwork_id for candidate in candidates] == ["100", "200"]
    path = service.apply_candidate(83, candidates[0])
    assert path.is_file() and path.read_bytes() == PNG and "_10_83" in path.name


def test_force_refresh_bypasses_existing_cache(tmp_path):
    provider = CandidateProvider(); service = ArtworkService(provider, tmp_path)
    existing = tmp_path / "fake-artwork_old_1.png"; existing.write_bytes(PNG)
    game = ExternalGame("old", "Game", "PC")
    assert service.fetch(1, game) == existing
    service.fetch(1, game, force=True)
    assert provider.search_calls == 1 and provider.download_calls == 1


def test_failed_refresh_does_not_replace_existing_file(tmp_path):
    provider = CandidateProvider(); service = ArtworkService(provider, tmp_path)
    existing = tmp_path / "fake-artwork_old_1.png"; existing.write_bytes(PNG)
    provider.body = b"<html>error</html>"; provider.content_type = "text/html"
    with pytest.raises(InvalidArtworkError): service.fetch(1, ExternalGame("old", "Game"), force=True)
    assert existing.read_bytes() == PNG


def test_remove_only_deletes_files_in_cover_cache(tmp_path):
    cache = tmp_path / "covers"; external = tmp_path / "user.png"
    cache.mkdir(); internal = cache / "cover.png"; internal.write_bytes(PNG); external.write_bytes(PNG)
    service = ArtworkService(CandidateProvider(), cache)
    service.remove(str(internal)); service.remove(str(external))
    assert not internal.exists() and external.exists()


class QueueDb:
    def __init__(self, count=3):
        self.rows = [{"id": n, "canonical_title": f"Game {n}", "title": f"Game {n}", "platform": "PC",
                      "release_date": None, "release_year": None, "external_game_id": str(n),
                      "artwork_external_game_id": None, "artwork_force_refresh": 0, "cover_path": None}
                     for n in range(count)]
        self.results = []

    def queued_covers(self): return self.rows
    def set_artwork_result(self, game_id, status, *args): self.results.append((game_id, status))
    def cover_path_is_shared(self, path, game_id): return False


class SlowArtwork:
    provider = CandidateProvider()
    def fetch_with_match(self, game_id, game, **kwargs):
        time.sleep(.03); return Path(f"/outside/{game_id}.png"), str(game_id)
    def remove(self, path): pass


def test_queue_progress_reports_actual_total():
    db = QueueDb(); progress = []
    stats = CoverQueueService(db, SlowArtwork(), 0).process(lambda *values: progress.append(values))
    assert [item[:2] for item in progress] == [(1, 3), (2, 3), (3, 3)]
    assert stats == {"processed": 3, "covered": 3, "ambiguous": 0, "failed": 0}


def test_cancel_while_paused_processes_no_game():
    db = QueueDb(); queue = CoverQueueService(db, SlowArtwork(), 0); queue.pause()
    thread = threading.Thread(target=queue.process); thread.start(); time.sleep(.03); queue.cancel(); thread.join(1)
    assert not thread.is_alive() and db.results == []
