from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from app.utils.paths import get_data_dir


@dataclass(slots=True)
class MetadataSettings:
    metadata_provider: str = "igdb"
    artwork_provider: str = "steamgriddb"
    igdb_client_id: str = ""
    igdb_client_secret: str = ""
    steamgriddb_api_key: str = ""
    automatic_search: bool = False
    automatic_covers: bool = True
    automatic_threshold: float = 90.0
    ambiguous_threshold: float = 75.0
    request_interval: float = 0.3

    @classmethod
    def load(cls, path: Path | None = None) -> "MetadataSettings":
        path = path or get_data_dir() / "settings.json"
        raw = json.loads(path.read_text("utf-8")) if path.exists() else {}
        allowed = {f.name for f in fields(cls)}
        values = {k: v for k, v in raw.items() if k in allowed}
        result = cls(**values)
        # Environment variables are preferable for secrets and never persisted.
        result.igdb_client_id = os.getenv("SCANDIEGO_IGDB_CLIENT_ID", result.igdb_client_id)
        result.igdb_client_secret = os.getenv("SCANDIEGO_IGDB_CLIENT_SECRET", result.igdb_client_secret)
        result.steamgriddb_api_key = os.getenv("SCANDIEGO_STEAMGRIDDB_API_KEY", result.steamgriddb_api_key)
        return result

    def save(self, path: Path | None = None) -> None:
        path = path or get_data_dir() / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), "utf-8")
