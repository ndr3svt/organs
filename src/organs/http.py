import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

TIMEOUT = (10, 25)  # connect, read. Short on purpose: a stalled socket should fail fast and be retried.
MAX_WAIT = 30  # seconds. A Retry-After longer than this is treated as "skip this request", not "wait".

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


def reset_session() -> None:
    """Drop pooled connections. A stale keep-alive socket otherwise fails every retry the same way."""
    global _session
    if _session is not None:
        _session.close()
    _session = None


def get(url: str, *, delay: float = 0.5, retries: int = 5, **kw) -> requests.Response:
    """Polite GET: minimum gap between calls; retry with backoff on 429/5xx and on network failures,
    each time on a fresh connection."""
    global _last
    for attempt in range(retries):
        wait = delay - (time.monotonic() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.monotonic()
        try:
            r = session().get(url, timeout=TIMEOUT, **kw)
        except (requests.ConnectionError, requests.Timeout):
            reset_session()
            if attempt == retries - 1:
                raise
            time.sleep(min(2 ** attempt, 8))
            continue
        if r.status_code in (429, 500, 502, 503, 504) and attempt < retries - 1:
            ra = r.headers.get("Retry-After", "")
            wait_s = int(ra) if ra.isdigit() else 0
            if wait_s > MAX_WAIT:  # a long ban (Wikimedia answers 600 s for some originals): skip, do not sleep on it
                raise requests.HTTPError(f"{r.status_code}, Retry-After {wait_s}s", response=r)
            time.sleep(max(wait_s, 2 ** (attempt + 1)))
            continue
        r.raise_for_status()
        return r
    raise RuntimeError("unreachable")
