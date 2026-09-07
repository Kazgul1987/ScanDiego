from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from app.utils.paths import get_data_dir
from app.services.credential_store import CredentialStore


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
    def load(cls, path: Path | None = None, credential_store: CredentialStore | None = None) -> "MetadataSettings":
        path = path or get_data_dir() / "settings.json"
        raw = json.loads(path.read_text("utf-8")) if path.exists() else {}
        allowed = {f.name for f in fields(cls)}
        values = {k: v for k, v in raw.items() if k in allowed}
        store = credential_store or CredentialStore()
        result = cls(**values)
        migrated = False
        for name in ("igdb_client_secret", "steamgriddb_api_key"):
            legacy = raw.get(name)
            if legacy and store.set(name, legacy): raw.pop(name, None); migrated = True
        # Environment variables are preferable for secrets and never persisted.
        result.igdb_client_id = os.getenv("SCANDIEGO_IGDB_CLIENT_ID", result.igdb_client_id)
        result.igdb_client_secret = store.get("igdb_client_secret") or (result.igdb_client_secret if not migrated else "")
        result.steamgriddb_api_key = store.get("steamgriddb_api_key") or (result.steamgriddb_api_key if not migrated else "")
        if migrated:
            path.write_text(json.dumps(raw, indent=2), "utf-8")
        return result

    def save(self, path: Path | None = None, credential_store: CredentialStore | None = None) -> None:
        path = path or get_data_dir() / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        store = credential_store or CredentialStore()
        secrets_ok = all(store.set(name, getattr(self, name)) for name in ("igdb_client_secret", "steamgriddb_api_key"))
        payload = asdict(self)
        payload.pop("igdb_client_secret"); payload.pop("steamgriddb_api_key")
        path.write_text(json.dumps(payload, indent=2), "utf-8")
        if not secrets_ok: raise RuntimeError("Credential Manager nicht verfügbar; Secrets wurden nicht gespeichert")
