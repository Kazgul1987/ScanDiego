from __future__ import annotations
from app.models.metadata import CoverResult, ExternalGame
from app.providers.base import ArtworkProvider, MetadataProvider


class FakeMetadataProvider(MetadataProvider):
    name = "fake"
    def __init__(self, games: list[ExternalGame] | None = None): self.games = games or []; self.search_calls = 0; self.get_calls = 0
    def search_game(self, title: str, platform: str) -> list[ExternalGame]: self.search_calls += 1; return list(self.games)
    def get_game(self, external_id: str) -> ExternalGame:
        self.get_calls += 1
        return next(game for game in self.games if game.external_id == str(external_id))


class FakeArtworkProvider(ArtworkProvider):
    name = "fake-artwork"
    def __init__(self, body: bytes = b"\x89PNG\r\n\x1a\ncontent", content_type="image/png"):
        self.body, self.content_type, self.download_calls = body, content_type, 0
    def search_cover(self, game: ExternalGame) -> list[CoverResult]: return [CoverResult("fake://cover", external_game_id=game.external_id)]
    def download_cover(self, cover: CoverResult) -> tuple[bytes, str]: self.download_calls += 1; return self.body, self.content_type
