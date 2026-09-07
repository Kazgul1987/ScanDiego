from __future__ import annotations

from abc import ABC, abstractmethod
from app.models.metadata import CoverResult, ExternalGame, ProviderHealthResult


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
    def health_check(self) -> ProviderHealthResult:
        return ProviderHealthResult(True, "ok", "Provider erreichbar")
