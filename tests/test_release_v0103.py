import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QApplication, QDialog, QListWidgetItem

from app.models.metadata import ArtworkCandidate, ExternalGame
from app.providers.steamgriddb import SteamGridDBProvider
from app.services.cover_queue_service import CoverQueueService
from app.ui.cover_selection_dialog import CoverSelectionDialog


class RouteSteamGridDB(SteamGridDBProvider):
    def __init__(self, preferred, fallback, games=None):
        super().__init__("test-key")
        self.preferred, self.fallback = preferred, fallback
        self.games = games or [{"id": 7, "name": "Test Game"}]
        self.paths = []

    def _get(self, path):
        self.paths.append(path)
        if path.startswith("/search/"):
            return self.games
        return self.preferred if "?dimensions=" in path else self.fallback


def grid(artwork_id, width, height, url=None):
    return {"id": artwork_id, "url": url or f"https://img/{artwork_id}.png",
            "width": width, "height": height}


def test_preferred_grids_avoid_unfiltered_request():
    provider = RouteSteamGridDB([grid(1, 600, 900)], [grid(2, 720, 1080)])
    covers = provider.covers_for_game("7")
    assert covers[0].width == 600
    assert provider.paths == ["/grids/game/7?dimensions=600x900,342x482,660x930"]


def test_empty_preferred_uses_ranked_deduplicated_portrait_fallback():
    fallback = [grid("tiny", 100, 100), grid("wide", 1920, 1080),
                grid("best", 720, 1080), grid("tall", 600, 1000),
                grid("best", 720, 1080, "https://duplicate")]
    provider = RouteSteamGridDB([], fallback)
    covers = provider.covers_for_game("7")
    assert [(cover.width, cover.height) for cover in covers] == [(720, 1080), (600, 1000)]
    assert provider.paths[-1] == "/grids/game/7"


def test_empty_fallback_is_normal_no_artwork_state():
    provider = RouteSteamGridDB([], [])
    assert provider.search_cover(ExternalGame("", "Test Game")) == []
    assert provider.last_search_status == "no_artwork"


def test_ambiguous_match_never_requests_grids(monkeypatch):
    provider = RouteSteamGridDB([], [grid(1, 720, 1080)],
                                 [{"id": 1, "name": "007 First Light"},
                                  {"id": 2, "name": "007 First Light Deluxe"}])
    monkeypatch.setattr(provider, "_rank_games", lambda game, games: [(96, games[0]), (93, games[1])])
    assert provider.search_cover(ExternalGame("", "007 First Light")) == []
    assert provider.last_search_status == "ambiguous"
    assert not any(path.startswith("/grids/") for path in provider.paths)


def test_manual_candidates_use_unfiltered_fallback():
    provider = RouteSteamGridDB([], [grid(1, 720, 1080)])
    candidates = provider.search_artwork_candidates(ExternalGame("", "Test Game"))
    assert len(candidates) == 1 and candidates[0].width == 720
    assert "/grids/game/7" in provider.paths


def test_bulk_queue_preserves_normal_no_artwork_status():
    class Db:
        row = {"id": 1, "canonical_title": "Test Game", "title": "Test Game", "platform": "PC",
               "release_date": None, "release_year": None, "external_game_id": "7",
               "artwork_external_game_id": None, "artwork_force_refresh": 0, "cover_path": None}
        def __init__(self): self.results = []
        def queued_covers(self): return [self.row]
        def set_artwork_result(self, game_id, status, *args): self.results.append((game_id, status))

    provider = RouteSteamGridDB([], [])
    class Artwork:
        def __init__(self): self.provider = provider
        def fetch_with_match(self, game_id, game, **kwargs):
            self.provider.search_cover(game)
            return None

    db = Db(); stats = CoverQueueService(db, Artwork(), interval=0).process()
    assert db.results[-1] == (1, "no_artwork")
    assert stats == {"processed": 1, "covered": 0, "ambiguous": 0, "failed": 0}


class SuccessfulWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, *args): super().__init__()

    @Slot()
    def run(self): self.finished.emit("cover.png")


class FailedWorker(SuccessfulWorker):
    @Slot()
    def run(self): self.failed.emit("download failed")


class SlowWorker(SuccessfulWorker):
    @Slot()
    def run(self):
        time.sleep(.08)
        self.finished.emit("cover.png")


def make_dialog(monkeypatch, worker_class):
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(CoverSelectionDialog, "_search", lambda self, title: None)
    monkeypatch.setattr(CoverSelectionDialog, "apply_worker_class", worker_class)
    row = {"id": 1, "title": "Test Game", "canonical_title": None, "external_game_id": None,
           "platform": "PC", "release_date": None, "release_year": None}
    dialog = CoverSelectionDialog(row, "unused.db", object())
    dialog.candidates = [ArtworkCandidate("1", "7", "Test Game", "https://img/1.png")]
    item = QListWidgetItem("cover"); item.setData(256, 0); dialog.list.addItem(item); dialog.list.setCurrentItem(item)
    return dialog


def process_until(predicate, timeout=.75):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QApplication.processEvents(); time.sleep(.005)
    assert predicate()


def test_successful_apply_accepts_only_after_thread_finishes_and_emits_once(monkeypatch):
    dialog = make_dialog(monkeypatch, SuccessfulWorker); emissions = []
    dialog.cover_applied.connect(lambda: emissions.append(True)); dialog._apply()
    thread = dialog._apply_thread
    assert dialog.result() != QDialog.DialogCode.Accepted
    process_until(lambda: dialog._apply_thread is None)
    assert not thread.isRunning() and dialog.result() == QDialog.DialogCode.Accepted
    assert emissions == [True]


def test_failed_apply_cleans_up_and_keeps_dialog_open(monkeypatch):
    dialog = make_dialog(monkeypatch, FailedWorker); emissions = []
    dialog.cover_applied.connect(lambda: emissions.append(True)); dialog._apply()
    thread = dialog._apply_thread
    process_until(lambda: dialog._apply_thread is None)
    assert not thread.isRunning() and dialog.result() != QDialog.DialogCode.Accepted
    assert emissions == [] and "download failed" in dialog.info.text()


def test_close_during_apply_is_deferred_safely(monkeypatch):
    dialog = make_dialog(monkeypatch, SlowWorker); dialog.show(); dialog._apply()
    dialog.close(); QApplication.processEvents()
    assert dialog.isVisible() and dialog._apply_thread is not None
    process_until(lambda: dialog._apply_thread is None)
    assert dialog.result() == QDialog.DialogCode.Accepted
