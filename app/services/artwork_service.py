from __future__ import annotations
import logging, os, tempfile
from pathlib import Path
from app.models.metadata import ArtworkCandidate, ExternalGame
from app.providers.base import ArtworkProvider
from app.utils.paths import get_covers_dir

LOGGER = logging.getLogger(__name__)
CONTENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAGIC = {"image/jpeg": (b"\xff\xd8\xff",), "image/png": (b"\x89PNG\r\n\x1a\n",), "image/webp": (b"RIFF",)}


class InvalidArtworkError(ValueError): pass


class ArtworkService:
    def __init__(self, provider: ArtworkProvider, cache_dir: Path | None = None):
        self.provider, self.cache_dir = provider, cache_dir or get_covers_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch(self, game_id: int, game: ExternalGame, force=False,
              artwork_external_id: str | None = None) -> Path | None:
        result = self.fetch_with_match(game_id, game, force, artwork_external_id)
        return result[0] if result else None

    def fetch_with_match(self, game_id: int, game: ExternalGame, force=False,
                         artwork_external_id: str | None = None) -> tuple[Path, str | None] | None:
        match_id = artwork_external_id or game.external_id
        prefix = f"{self.provider.name}_{match_id}_{game_id}"
        existing = next(iter(self.cache_dir.glob(prefix + ".*")), None)
        if existing and not force: return existing, artwork_external_id
        direct = getattr(self.provider, "covers_for_game", None)
        covers = direct(artwork_external_id) if artwork_external_id and direct else self.provider.search_cover(game)
        if not covers: return None
        body, content_type = self.provider.download_cover(covers[0])
        target = self._write_validated(body, content_type, prefix)
        return target, covers[0].external_game_id or artwork_external_id

    def apply_candidate(self, game_id: int, candidate: ArtworkCandidate) -> Path:
        body, content_type = self.provider.download_candidate(candidate)
        prefix = f"{self.provider.name}_{candidate.external_game_id}_{game_id}"
        return self._write_validated(body, content_type, prefix)

    def _write_validated(self, body: bytes, content_type: str, prefix: str) -> Path:
        content_type = content_type.split(";", 1)[0].lower()
        if content_type not in CONTENT_TYPES or not body or not body.startswith(MAGIC[content_type]): raise InvalidArtworkError("Ungültige Bildantwort")
        if content_type == "image/webp" and (len(body) < 12 or body[8:12] != b"WEBP"): raise InvalidArtworkError("Ungültiges WebP")
        target = self.cache_dir / (prefix + CONTENT_TYPES[content_type])
        fd, temp_name = tempfile.mkstemp(dir=self.cache_dir, prefix=".cover-")
        try:
            with os.fdopen(fd, "wb") as out: out.write(body); out.flush(); os.fsync(out.fileno())
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name): os.unlink(temp_name)
        LOGGER.info("Cover gespeichert: %s", target.name)
        return target

    def remove(self, path: str | None) -> None:
        if path and self.is_cache_path(path):
            try: Path(path).unlink(missing_ok=True)
            except OSError: LOGGER.exception("Cover konnte nicht entfernt werden")

    def is_cache_path(self, path: str | Path) -> bool:
        try:
            return Path(path).resolve().parent == self.cache_dir.resolve()
        except (OSError, RuntimeError):
            return False
