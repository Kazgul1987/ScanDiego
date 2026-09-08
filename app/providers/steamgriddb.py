from __future__ import annotations
import urllib.parse
import time
import logging
from difflib import SequenceMatcher
from app.models.metadata import ArtworkCandidate, CoverResult, ExternalGame, ProviderHealthResult
from app.providers.base import ArtworkProvider
from app.services.http_client import HttpClient, NetworkError

LOGGER = logging.getLogger(__name__)


class SteamGridDBProvider(ArtworkProvider):
    name = "steamgriddb"
    MIN_MATCH_SCORE = 75
    MAX_MANUAL_GAME_MATCHES = 3
    MANUAL_SCORE_WINDOW = 20
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
        ranked = self._rank_games(game, games)
        self.last_candidates = [{"id": str(item.get("id")), "title": item.get("name") or "", "score": value}
                                for value, item in ranked[:10]]
        for candidate in self.last_candidates:
            LOGGER.debug('Artwork candidate id=%s title="%s" score=%.1f', candidate["id"], candidate["title"], candidate["score"])
        if ranked[0][0] < self.MIN_MATCH_SCORE:
            LOGGER.info("Artwork match rejected best=%.1f", ranked[0][0]); return []
        if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 5:
            best, second = ranked[0], ranked[1]
            LOGGER.info('Artwork match ambiguous title="%s" best_title="%s" best_id=%s best_score=%.1f '
                        'second_title="%s" second_id=%s second_score=%.1f delta=%.1f', game.title,
                        best[1].get("name"), best[1].get("id"), best[0], second[1].get("name"),
                        second[1].get("id"), second[0], best[0] - second[0]); return []
        LOGGER.info("Artwork match accepted id=%s score=%.1f", ranked[0][1].get("id"), ranked[0][0])
        return self.covers_for_game(str(ranked[0][1]["id"]))

    @staticmethod
    def _rank_games(game: ExternalGame, games: list[dict]) -> list[tuple[float, dict]]:
        def score(item):
            title = item.get("name") or ""
            value = SequenceMatcher(None, game.title.casefold(), title.casefold()).ratio() * 100
            year = item.get("release_date") or item.get("year")
            if game.release_year and year:
                try: value += max(0, 5 - abs(int(str(year)[:4]) - game.release_year))
                except ValueError: pass
            return value
        return sorted(((score(item), item) for item in games), reverse=True, key=lambda x: x[0])
    def covers_for_game(self, external_id: str) -> list[CoverResult]:
        grids = self._get(f"/grids/game/{external_id}?dimensions=600x900,342x482,660x930") or []
        return [CoverResult(x["url"], "poster", x.get("width"), x.get("height"), str(external_id)) for x in grids]
    def search_artwork_candidates(self, game: ExternalGame, limit: int = 10) -> list[ArtworkCandidate]:
        if limit <= 0:
            return []
        games = self._get("/search/autocomplete/" + urllib.parse.quote(game.title)) or []
        ranked = self._rank_games(game, games)
        if not ranked:
            return []
        best_score = ranked[0][0]
        plausible = [(score, match) for score, match in ranked
                     if score >= self.MIN_MATCH_SCORE and score >= best_score - self.MANUAL_SCORE_WINDOW]
        plausible = plausible[:min(self.MAX_MANUAL_GAME_MATCHES, limit)]
        candidates: list[ArtworkCandidate] = []
        seen: set[tuple[str, str]] = set()
        grids_by_game: list[tuple[float, dict, list[dict]]] = []
        for score, match in plausible:
            external_id = str(match.get("id"))
            grids = self._get(f"/grids/game/{external_id}?dimensions=600x900,342x482,660x930") or []
            grids_by_game.append((score, match, grids))

        # Round-robin preserves rank order while preventing the first game from
        # consuming the global budget. With one match it naturally uses all slots.
        index = 0
        while len(candidates) < limit and any(index < len(grids) for _, _, grids in grids_by_game):
            for score, match, grids in grids_by_game:
                if index >= len(grids) or len(candidates) >= limit:
                    continue
                grid = grids[index]
                external_id = str(match.get("id"))
                artwork_id = str(grid.get("id")) if grid.get("id") is not None else ""
                key = ("id", artwork_id) if artwork_id else ("url", grid["url"])
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(ArtworkCandidate(artwork_id, external_id, match.get("name") or "",
                    grid["url"], grid.get("thumb") or grid.get("url"), grid.get("width"), grid.get("height"), score,
                    grid.get("style"), tuple(grid.get("tags") or ())))
            index += 1
        for score, match, grids in grids_by_game:
            count = sum(candidate.external_game_id == str(match.get("id")) for candidate in candidates)
            LOGGER.debug('game_match id=%s title="%s" score=%.1f covers=%d', match.get("id"),
                         match.get("name") or "", score, count)
        LOGGER.info('Manual artwork search game_id=%s title="%s" plausible_games=%d candidates=%d',
                    game.external_id, game.title, len(plausible), len(candidates))
        return candidates
    def download_cover(self, cover: CoverResult) -> tuple[bytes, str]:
        response = self.http.request(cover.url)
        return response.body, response.content_type
    def health_check(self) -> ProviderHealthResult:
        started=time.monotonic()
        try: self._get("/search/autocomplete/ScanDiego"); return ProviderHealthResult(True,"ok","Credentials gültig",(time.monotonic()-started)*1000)
        except NetworkError as exc: return ProviderHealthResult(False,"credentials",str(exc),(time.monotonic()-started)*1000)
