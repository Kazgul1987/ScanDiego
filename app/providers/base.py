from __future__ import annotations

from abc import ABC, abstractmethod
from app.models.metadata import ArtworkCandidate, CoverResult, ExternalGame, ProviderHealthResult


class MetadataProvider(ABC):
    name: str
    @abstractmethod
    def search_game(self, title: str, platform: str) -> list[ExternalGame]: ...
    @abstractmethod
    def get_game(self, external_id: str) -> ExternalGame: ...
    def health_check(self) -> ProviderHealthResult:
        return ProviderHealthResult(True, "ok", "Provider erreichbar")


class ArtworkProvider(ABC):
    name: str
    @abstractmethod
    def search_cover(self, game: ExternalGame) -> list[CoverResult]: ...
    @abstractmethod
    def download_cover(self, cover: CoverResult) -> tuple[bytes, str]: ...
    def search_artwork_candidates(self, game: ExternalGame, limit: int = 10) -> list[ArtworkCandidate]:
        return []
    def download_candidate(self, candidate: ArtworkCandidate) -> tuple[bytes, str]:
        return self.download_cover(CoverResult(candidate.image_url, width=candidate.width,
                                   height=candidate.height, external_game_id=candidate.external_game_id))
    def health_check(self) -> ProviderHealthResult:
        return ProviderHealthResult(True, "ok", "Provider erreichbar")
