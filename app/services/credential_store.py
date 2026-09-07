from __future__ import annotations
import logging, os

LOGGER = logging.getLogger(__name__)
SERVICE = "ScanDiego"
ENV = {"igdb_client_secret": "SCANDIEGO_IGDB_CLIENT_SECRET",
       "steamgriddb_api_key": "SCANDIEGO_STEAMGRIDDB_API_KEY"}

class CredentialStore:
    """Environment-first secret access with an optional OS credential backend."""
    def __init__(self, backend=None):
        if backend is not None: self.backend = backend
        else:
            try:
                import keyring
                self.backend = keyring
            except ImportError: self.backend = None
    def get(self, name: str) -> str:
        if os.getenv(ENV[name]): return os.environ[ENV[name]]
        if not self.backend: return ""
        try: return self.backend.get_password(SERVICE, name) or ""
        except Exception:
            LOGGER.warning("Credential Manager für %s ist nicht verfügbar", name); return ""
    def set(self, name: str, value: str) -> bool:
        if not value: return True
        if not self.backend: return False
        try: self.backend.set_password(SERVICE, name, value); return True
        except Exception:
            LOGGER.warning("Secret konnte nicht im Credential Manager gespeichert werden: %s", name); return False
