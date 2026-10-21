"""HTTP sessions that identify us politely to agencies that require it."""

import threading
import time
from urllib.parse import urlparse

import requests

USER_AGENT = "Ajai Upadhyaya research ajaiupad@gmail.com"
SEC_MIN_INTERVAL = 0.1  # seconds between requests: at most 10 per second


# Shared across every throttled session, so separate fetches and retries are paced together.
_throttle_lock = threading.Lock()
_last_request: float | None = None


class _ThrottledSession(requests.Session):
    def __init__(self, min_interval: float):
        super().__init__()
        self._min_interval = min_interval

    def request(self, *args, **kwargs):
        global _last_request
        with _throttle_lock:
            if _last_request is not None:
                wait = self._min_interval - (time.monotonic() - _last_request)
                if wait > 0:
                    time.sleep(wait)
            _last_request = time.monotonic()
        return super().request(*args, **kwargs)


def _host_is(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def session_for(url: str) -> requests.Session:
    host = (urlparse(url).hostname or "").lower()
    if _host_is(host, "sec.gov"):
        session = _ThrottledSession(SEC_MIN_INTERVAL)
        session.headers["User-Agent"] = USER_AGENT
    elif _host_is(host, "bls.gov"):
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT
    else:
        session = requests.Session()
    return session
