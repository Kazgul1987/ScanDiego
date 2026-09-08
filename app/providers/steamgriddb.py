from __future__ import annotations
import urllib.parse
import time
import logging
from difflib import SequenceMatcher
from app.models.metadata import CoverResult, ExternalGame, ProviderHealthResult
from app.providers.base import ArtworkProvider
from app.services.http_client import HttpClient, NetworkError

LOGGER = logging.getLogger(__name__)


class SteamGridDBProvider(ArtworkProvider):
    name = "steamgriddb"
    def __init__(self, api_key: str, http: HttpClient | None = None):
        self._key, self.http = api_key, http or HttpClient()
        self.last_candidates: list[dict] = []
    def _get(self, path: str):
        if not self._key: raise NetworkError("SteamGridDB-API-Key fehlt")
        return self.http.request("https://www.steamgriddb.com/api/v2" + path, headers={"Authorization": "Bearer " + self._key}).json().get("data")
    def search_cover(self, game: ExternalGame) -> list[CoverResult]:
        LOGGER.info('Artwork search title="%s" platform="%s" year=%s', game.title, game.platform, game.release_year)
        games = self._get("/search/autocomplete/" + urllib.parse.quote(game.title)) or []
        if not games: return []
        def score(item):
            title = item.get("name") or ""
            value = SequenceMatcher(None, game.title.casefold(), title.casefold()).ratio() * 100
            year = item.get("release_date") or item.get("year")
            if game.release_year and year:
                try: value += max(0, 5 - abs(int(str(year)[:4]) - game.release_year))
                except ValueError: pass
            return value
        ranked = sorted(((score(item), item) for item in games), reverse=True, key=lambda x: x[0])
        self.last_candidates = [{"id": str(item.get("id")), "title": item.get("name") or "", "score": value}
                                for value, item in ranked[:10]]
        for candidate in self.last_candidates:
            LOGGER.debug('Artwork candidate id=%s title="%s" score=%.1f', candidate["id"], candidate["title"], candidate["score"])
        if ranked[0][0] < 75:
            LOGGER.info("Artwork match rejected best=%.1f", ranked[0][0]); return []
        if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 5:
            LOGGER.info("Artwork match ambiguous best=%.1f second=%.1f delta=%.1f",
                        ranked[0][0], ranked[1][0], ranked[0][0] - ranked[1][0]); return []
        LOGGER.info("Artwork match accepted id=%s score=%.1f", ranked[0][1].get("id"), ranked[0][0])
        return self.covers_for_game(str(ranked[0][1]["id"]))
    def covers_for_game(self, external_id: str) -> list[CoverResult]:
        grids = self._get(f"/grids/game/{external_id}?dimensions=600x900,342x482,660x930") or []
        return [CoverResult(x["url"], "poster", x.get("width"), x.get("height"), str(external_id)) for x in grids]
    def download_cover(self, cover: CoverResult) -> tuple[bytes, str]:
        response = self.http.request(cover.url)
        return response.body, response.content_type
    def health_check(self) -> ProviderHealthResult:
        started=time.monotonic()
        try: self._get("/search/autocomplete/ScanDiego"); return ProviderHealthResult(True,"ok","Credentials gültig",(time.monotonic()-started)*1000)
        except NetworkError as exc: return ProviderHealthResult(False,"credentials",str(exc),(time.monotonic()-started)*1000)
