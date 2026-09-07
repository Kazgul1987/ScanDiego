from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)


class NetworkError(RuntimeError): pass
class RateLimitError(NetworkError):
    def __init__(self, message: str, retry_after: float = 1.0):
        super().__init__(message); self.retry_after = retry_after


@dataclass(slots=True)
class HttpResponse:
    body: bytes
    content_type: str
    status: int

    def json(self):
        try: return json.loads(self.body.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc: raise NetworkError("Ungültige JSON-Antwort") from exc


class HttpClient:
    """Small synchronous client intended for worker threads, with bounded retries."""
    def __init__(self, timeout: float = 15, retries: int = 2, min_interval: float = .25):
        self.timeout, self.retries, self.min_interval = timeout, retries, min_interval
        self._last_request = 0.0

    def request(self, url: str, *, method="GET", headers=None, data: bytes | None = None) -> HttpResponse:
        headers = {"User-Agent": "ScanDiego/0.8", **(headers or {})}
        for attempt in range(self.retries + 1):
            time.sleep(max(0, self.min_interval - (time.monotonic() - self._last_request)))
            try:
                self._last_request = time.monotonic()
                with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method=method), timeout=self.timeout) as response:
                    return HttpResponse(response.read(), response.headers.get_content_type(), response.status)
            except urllib.error.HTTPError as exc:
                retry_after = float(exc.headers.get("Retry-After", "1") or 1)
                if exc.code == 429:
                    LOGGER.warning("Provider-Rate-Limit; Retry nach %.1fs", retry_after)
                    if attempt == self.retries: raise RateLimitError("Provider-Rate-Limit", retry_after) from exc
                    time.sleep(min(retry_after, 30)); continue
                if exc.code not in (500, 502, 503, 504) or attempt == self.retries:
                    raise NetworkError(f"HTTP {exc.code}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt == self.retries: raise NetworkError(f"Netzwerkfehler: {exc.reason if hasattr(exc, 'reason') else exc}") from exc
            time.sleep(2 ** attempt)
        raise NetworkError("Anfrage fehlgeschlagen")
