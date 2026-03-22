"""LinkedIn public page scraper — extracts employee count from public company pages."""

import re
import logging
from datetime import datetime, timedelta
from scrapers.base import BaseScraper
from config import Config

logger = logging.getLogger(__name__)


class LinkedInScraper(BaseScraper):
    """Scrape public LinkedIn company pages for employee count.

    Uses respectful scraping: cached results, proper headers, rate limiting.
    Falls back gracefully if blocked or unavailable.
    """

    def __init__(self):
        super().__init__("linkedin")
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-GB,en;q=0.9",
        })
        self._cache = {}

    def get_employee_count(self, linkedin_url):
        """Extract employee count from a public LinkedIn company page.

        Returns dict with employee_count and source, or empty dict on failure.
        """
        if not linkedin_url:
            return {}

        # Check cache
        cache_entry = self._cache.get(linkedin_url)
        if cache_entry:
            cached_at, data = cache_entry
            if datetime.utcnow() - cached_at < timedelta(days=Config.LINKEDIN_CACHE_DAYS):
                return data

        # Normalize URL
        url = linkedin_url.rstrip("/")
        if not url.endswith("/"):
            url += "/"

        html = self.get_html(url)
        if not html:
            logger.warning(f"[{self.name}] Could not fetch {linkedin_url}")
            return {}

        employee_count = self._extract_employee_count(html)
        if employee_count:
            result = {
                "employee_count": employee_count,
                "source": "linkedin",
            }
            self._cache[linkedin_url] = (datetime.utcnow(), result)
            logger.info(f"[{self.name}] {linkedin_url} → {employee_count} employees")
            return result

        logger.info(f"[{self.name}] Could not extract employee count from {linkedin_url}")
        return {}

    def _extract_employee_count(self, html):
        """Try multiple patterns to extract employee count from LinkedIn HTML."""
        patterns = [
            # JSON-LD structured data
            r'"numberOfEmployees"\s*:\s*\{\s*"@type"\s*:\s*"QuantitativeValue"\s*,\s*"value"\s*:\s*(\d+)',
            # Meta tag
            r'<meta[^>]*content="(\d[\d,]+)\s*(?:employees|associated members|followers)"',
            # Visible text patterns
            r'(\d[\d,]+)\s+employees\s+on\s+LinkedIn',
            r'(\d[\d,]+)\s+associated\s+members',
            # Company size in About section
            r'Company size[^<]*?(\d[\d,]+)\s*[-–]\s*(\d[\d,]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                try:
                    # If it's a range pattern (e.g. 1,001-5,000), take midpoint
                    if match.lastindex and match.lastindex >= 2:
                        low = int(match.group(1).replace(",", ""))
                        high = int(match.group(2).replace(",", ""))
                        return (low + high) // 2
                    return int(match.group(1).replace(",", ""))
                except (ValueError, IndexError):
                    continue

        return None
