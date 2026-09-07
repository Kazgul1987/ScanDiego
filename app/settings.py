from __future__ import annotations

import json
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
        credentials = ("igdb_client_id", "igdb_client_secret", "steamgriddb_api_key")
        migrated = False
        for name in credentials:
            legacy = raw.get(name)
            stored = store.get(name)
            if legacy and not stored:
                if store.set(name, legacy):
                    stored = store.get(name) or legacy
                    raw.pop(name, None)
                    migrated = True
            elif legacy and stored:
                raw.pop(name, None)
                migrated = True
            setattr(result, name, stored or legacy or "")
        if migrated:
            path.write_text(json.dumps(raw, indent=2), "utf-8")
        return result

    def save(self, path: Path | None = None, credential_store: CredentialStore | None = None) -> None:
        path = path or get_data_dir() / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        store = credential_store or CredentialStore()
        credentials = ("igdb_client_id", "igdb_client_secret", "steamgriddb_api_key")
        credentials_ok = all(store.set(name, getattr(self, name)) for name in credentials)
        payload = asdict(self)
        for name in credentials:
            payload.pop(name)
        path.write_text(json.dumps(payload, indent=2), "utf-8")
        if not credentials_ok:
            raise RuntimeError("Windows Credential Manager ist nicht verfügbar. "
                               "Die Provider-Zugangsdaten konnten nicht dauerhaft gespeichert werden.")
