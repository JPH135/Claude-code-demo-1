"""Google News RSS scraper — free, no API key required."""

import logging
from datetime import datetime, timedelta
from urllib.parse import quote_plus
import requests
import atoma
from config import Config

logger = logging.getLogger(__name__)


def _parse_rss(url):
    """Fetch and parse an RSS feed using atoma."""
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "FintechScanner/1.0",
        })
        resp.raise_for_status()
        return atoma.parse_rss_bytes(resp.content)
    except Exception as e:
        logger.warning(f"Failed to parse RSS from {url}: {e}")
        return None


class GoogleNewsScraper:
    """Fetch recent news for a company via Google News RSS feeds."""

    def __init__(self):
        self.name = "google_news"

    def fetch_news(self, company_name, max_articles=10):
        """Fetch recent news articles for a company from Google News RSS."""
        query = quote_plus(f'"{company_name}" fintech')
        url = f"https://news.google.com/rss/search?q={query}&hl=en-GB&gl=GB&ceid=GB:en"

        feed = _parse_rss(url)
        if not feed:
            return []

        cutoff = datetime.utcnow() - timedelta(days=Config.NEWS_MAX_AGE_DAYS)
        articles = []

        for item in feed.items[:max_articles]:
            published = item.pub_date
            if published:
                # Convert to naive UTC datetime for comparison
                published_naive = published.replace(tzinfo=None) if published.tzinfo else published
                if published_naive < cutoff:
                    continue

            # Extract source from title (Google News format: "Title - Source")
            title = item.title or ""
            source = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0]
                source = parts[1] if len(parts) > 1 else ""

            articles.append({
                "title": title,
                "url": item.link or "",
                "published_date": published.date() if published else None,
                "source_name": source,
                "snippet": (item.description or "")[:500],
            })

        logger.info(f"[{self.name}] Found {len(articles)} articles for {company_name}")
        return articles

    def fetch_fintech_industry_news(self, max_articles=20):
        """Fetch general UK/EU fintech industry news."""
        queries = [
            '"fintech" "UK" funding',
            '"fintech" "Europe" investment',
            'fintech startup series funding round',
        ]
        all_articles = []
        seen_urls = set()

        for query in queries:
            encoded = quote_plus(query)
            url = f"https://news.google.com/rss/search?q={encoded}&hl=en-GB&gl=GB&ceid=GB:en"
            feed = _parse_rss(url)
            if not feed:
                continue

            for item in feed.items[:max_articles]:
                link = item.link or ""
                if link in seen_urls:
                    continue
                seen_urls.add(link)

                published = item.pub_date

                title = item.title or ""
                source = ""
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    title = parts[0]
                    source = parts[1] if len(parts) > 1 else ""

                all_articles.append({
                    "title": title,
                    "url": link,
                    "published_date": published.date() if published else None,
                    "source_name": source,
                    "snippet": (item.description or "")[:500],
                })

        return all_articles[:max_articles]
