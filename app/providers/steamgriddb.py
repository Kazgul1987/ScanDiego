from __future__ import annotations
import urllib.parse
from app.models.metadata import CoverResult, ExternalGame
from app.providers.base import ArtworkProvider
from app.services.http_client import HttpClient, NetworkError


class SteamGridDBProvider(ArtworkProvider):
    name = "steamgriddb"
    def __init__(self, api_key: str, http: HttpClient | None = None): self._key, self.http = api_key, http or HttpClient()
    def _get(self, path: str):
        if not self._key: raise NetworkError("SteamGridDB-API-Key fehlt")
        return self.http.request("https://www.steamgriddb.com/api/v2" + path, headers={"Authorization": "Bearer " + self._key}).json().get("data")
    def search_cover(self, game: ExternalGame) -> list[CoverResult]:
        games = self._get("/search/autocomplete/" + urllib.parse.quote(game.title)) or []
        if not games: return []
        grids = self._get(f"/grids/game/{games[0]['id']}?dimensions=600x900,342x482,660x930") or []
        return [CoverResult(x["url"], "poster", x.get("width"), x.get("height")) for x in grids]
    def download_cover(self, cover: CoverResult) -> tuple[bytes, str]:
        response = self.http.request(cover.url)
        return response.body, response.content_type
