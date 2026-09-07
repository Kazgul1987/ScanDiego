from __future__ import annotations
import logging, os, tempfile
from pathlib import Path
from app.models.metadata import ExternalGame
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

    def fetch(self, game_id: int, game: ExternalGame, force=False) -> Path | None:
        prefix = f"{self.provider.name}_{game.external_id}_{game_id}"
        existing = next(iter(self.cache_dir.glob(prefix + ".*")), None)
        if existing and not force: return existing
        covers = self.provider.search_cover(game)
        if not covers: return None
        body, content_type = self.provider.download_cover(covers[0]); content_type = content_type.split(";", 1)[0].lower()
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
        if path:
            try: Path(path).unlink(missing_ok=True)
            except OSError: LOGGER.exception("Cover konnte nicht entfernt werden")
