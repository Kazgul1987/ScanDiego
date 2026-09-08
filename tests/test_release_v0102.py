import ast
from pathlib import Path

from app.models.metadata import ExternalGame
from app.providers.steamgriddb import SteamGridDBProvider


class StubSteamGridDB(SteamGridDBProvider):
    def __init__(self, games, grids):
        super().__init__("test-key")
        self.games = games
        self.grids = grids
        self.grid_requests = []

    def _get(self, path):
        if path.startswith("/search/"):
            return self.games
        game_id = path.split("/grids/game/", 1)[1].split("?", 1)[0]
        self.grid_requests.append(game_id)
        return self.grids.get(game_id, [])


def grids(game_id, count, duplicate_id=None):
    values = [{"id": f"{game_id}-{index}", "url": f"https://img/{game_id}/{index}.png",
               "width": 600, "height": 900} for index in range(count)]
    if duplicate_id is not None:
        values.append({"id": duplicate_id, "url": "https://img/duplicate.png"})
    return values


def test_ambiguous_games_share_candidate_limit():
    provider = StubSteamGridDB(
        [{"id": 100, "name": "007 First Light"}, {"id": 200, "name": "007 First Light Deluxe"}],
        {"100": grids(100, 20), "200": grids(200, 8)},
    )
    candidates = provider.search_artwork_candidates(ExternalGame("83", "007 First Light"), limit=10)
    assert len(candidates) == 10
    assert {candidate.external_game_id for candidate in candidates} == {"100", "200"}
    assert {candidate.game_title for candidate in candidates} == {"007 First Light", "007 First Light Deluxe"}


def test_single_game_can_use_entire_global_limit():
    provider = StubSteamGridDB([{"id": 100, "name": "007 First Light"}], {"100": grids(100, 12)})
    candidates = provider.search_artwork_candidates(ExternalGame("83", "007 First Light"), limit=10)
    assert len(candidates) == 10
    assert {candidate.external_game_id for candidate in candidates} == {"100"}


def test_implausible_game_is_not_requested_or_displayed():
    provider = StubSteamGridDB(
        [{"id": 100, "name": "007 First Light"}, {"id": 200, "name": "007 First Light Deluxe"},
         {"id": 300, "name": "Completely Wrong Game"}],
        {"100": grids(100, 4), "200": grids(200, 4), "300": grids(300, 4)},
    )
    candidates = provider.search_artwork_candidates(ExternalGame("83", "007 First Light"), limit=12)
    assert "300" not in provider.grid_requests
    assert {candidate.external_game_id for candidate in candidates} == {"100", "200"}


def test_three_games_obey_global_limit_and_artwork_ids_are_deduplicated(monkeypatch):
    provider = StubSteamGridDB(
        [{"id": 100, "name": "A"}, {"id": 200, "name": "B"}, {"id": 300, "name": "C"}],
        {"100": grids(100, 20, "shared"), "200": grids(200, 20, "shared"), "300": grids(300, 20)},
    )
    monkeypatch.setattr(provider, "_rank_games", lambda game, games: [(96, games[0]), (93, games[1]), (89, games[2])])
    provider.grids["100"][0]["id"] = "shared"
    provider.grids["200"][0]["id"] = "shared"
    candidates = provider.search_artwork_candidates(ExternalGame("83", "007 First Light"), limit=12)
    assert len(candidates) <= 12
    assert {candidate.external_game_id for candidate in candidates} == {"100", "200", "300"}
    ids = [candidate.artwork_id for candidate in candidates]
    assert len(ids) == len(set(ids))


def test_metadata_signals_are_each_connected_once():
    """Keep this regression runnable on CI hosts without Qt's libGL dependency."""
    source = Path("app/ui/main_window.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    method = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef) and node.name == "_start_metadata_queue")
    method_source = ast.get_source_segment(source, method)
    assert method_source.count("started.connect(self.metadata_worker.run)") == 1
    assert method_source.count("finished.connect(self._metadata_finished)") == 1
    assert method_source.count("failed.connect(self._metadata_failed)") == 1
