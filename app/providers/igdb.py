from __future__ import annotations

import logging, time, urllib.parse
from app.models.metadata import ExternalGame
from app.providers.base import MetadataProvider
from app.services.http_client import HttpClient, NetworkError

LOGGER = logging.getLogger(__name__)


class IGDBProvider(MetadataProvider):
    name = "igdb"
    def __init__(self, client_id: str, client_secret: str, http: HttpClient | None = None):
        self.client_id, self._secret, self.http = client_id, client_secret, http or HttpClient()
        self._token = ""; self._expires = 0.0

    def _access_token(self) -> str:
        if not self.client_id or not self._secret: raise NetworkError("IGDB-Credentials fehlen")
        if self._token and time.time() < self._expires - 60: return self._token
        query = urllib.parse.urlencode({"client_id": self.client_id, "client_secret": self._secret, "grant_type": "client_credentials"})
        data = self.http.request("https://id.twitch.tv/oauth2/token?" + query, method="POST").json()
        self._token, self._expires = data["access_token"], time.time() + int(data.get("expires_in", 0))
        return self._token

    def _query(self, body: str):
        LOGGER.info("IGDB Provider-Anfrage")
        return self.http.request("https://api.igdb.com/v4/games", method="POST", data=body.encode(), headers={"Client-ID": self.client_id, "Authorization": "Bearer " + self._access_token()}).json()

    @staticmethod
    def _map(item) -> ExternalGame:
        platforms = item.get("platforms") or []
        first = platforms[0] if platforms else {}
        release = item.get("first_release_date")
        year = time.gmtime(release).tm_year if release else None
        companies = item.get("involved_companies") or []
        return ExternalGame(str(item["id"]), item.get("name", ""), first.get("name", ""), str(first.get("id")) if first else None,
                            release_year=year, publisher=next((x["company"]["name"] for x in companies if x.get("publisher")), None),
                            developer=next((x["company"]["name"] for x in companies if x.get("developer")), None), description=item.get("summary"))

    def search_game(self, title: str, platform: str) -> list[ExternalGame]:
        safe = title.replace('"', '\\"')
        return [self._map(x) for x in self._query(f'search "{safe}"; fields name,summary,first_release_date,platforms.id,platforms.name,involved_companies.developer,involved_companies.publisher,involved_companies.company.name; limit 20;')]

    def get_game(self, external_id: str) -> ExternalGame:
        rows = self._query(f"where id = {int(external_id)}; fields name,summary,first_release_date,platforms.id,platforms.name,involved_companies.developer,involved_companies.publisher,involved_companies.company.name; limit 1;")
        if not rows: raise NetworkError("IGDB-Spiel nicht gefunden")
        return self._map(rows[0])

    def health_check(self) -> bool: self._access_token(); return True
