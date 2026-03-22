import time
import logging
import requests
from config import Config

logger = logging.getLogger(__name__)


class BaseScraper:
    """Base scraper with rate limiting, retry logic, and session management."""

    def __init__(self, name="base"):
        self.name = name
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "FintechScanner/1.0 (Investment Research Tool)",
            "Accept": "application/json, text/html",
        })
        self._last_request_time = 0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < Config.RATE_LIMIT_DELAY:
            time.sleep(Config.RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def get(self, url, params=None, headers=None, timeout=None, retries=3):
        self._rate_limit()
        timeout = timeout or Config.REQUEST_TIMEOUT

        for attempt in range(retries):
            try:
                resp = self.session.get(url, params=params, headers=headers, timeout=timeout)
                if resp.status_code == 429:
                    wait = min(2 ** (attempt + 1), 30)
                    logger.warning(f"[{self.name}] Rate limited, waiting {wait}s")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                if attempt < retries - 1:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"[{self.name}] Request failed ({e}), retrying in {wait}s")
                    time.sleep(wait)
                else:
                    logger.error(f"[{self.name}] Request failed after {retries} attempts: {e}")
                    return None

    def get_json(self, url, params=None, headers=None):
        resp = self.get(url, params=params, headers=headers)
        if resp is not None:
            try:
                return resp.json()
            except ValueError:
                logger.error(f"[{self.name}] Invalid JSON response from {url}")
        return None

    def get_html(self, url, params=None):
        resp = self.get(url, params=params)
        if resp is not None:
            return resp.text
        return None
