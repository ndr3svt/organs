import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

_session: requests.Session | None = None
_last = 0.0


def session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers["User-Agent"] = os.getenv(
            "INATURALIST_USER_AGENT", "organs/0.1 (research; private dataset)"
        )
    return _session


def get(url: str, *, delay: float = 0.5, retries: int = 3, **kw) -> requests.Response:
    """Polite GET: minimum gap between calls, retry with backoff on 429/5xx."""
    global _last
    for attempt in range(retries):
        wait = delay - (time.monotonic() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.monotonic()
        r = session().get(url, timeout=30, **kw)
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** (attempt + 1))
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()
    return r
