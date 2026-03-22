"""Sifted and Tech.eu RSS feeds — EU fintech industry news."""

import re
import logging
from datetime import datetime, timedelta
import requests
import atoma

logger = logging.getLogger(__name__)

FEEDS = [
    {"name": "Sifted", "url": "https://sifted.eu/feed"},
    {"name": "Tech.eu", "url": "https://tech.eu/feed"},
    {"name": "AltFi", "url": "https://www.altfi.com/rss"},
    {"name": "Finextra", "url": "https://www.finextra.com/rss/headlines.aspx"},
]


def _parse_feed(url):
    """Fetch and parse an RSS/Atom feed."""
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "FintechScanner/1.0",
        })
        resp.raise_for_status()
        content = resp.content
        # Try RSS first, then Atom
        try:
            return "rss", atoma.parse_rss_bytes(content)
        except Exception:
            try:
                return "atom", atoma.parse_atom_bytes(content)
            except Exception:
                return None, None
    except Exception as e:
        logger.warning(f"Failed to fetch feed {url}: {e}")
        return None, None


class FintechNewsScraper:
    """Aggregate fintech news from EU-focused RSS feeds."""

    def __init__(self):
        self.name = "fintech_news"

    def fetch_all_feeds(self, max_age_days=7, max_per_feed=20):
        """Fetch recent articles from all configured fintech news feeds."""
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        all_articles = []

        for feed_config in FEEDS:
            articles = self._fetch_feed(feed_config, cutoff, max_per_feed)
            all_articles.extend(articles)

        # Sort by date, newest first
        all_articles.sort(key=lambda a: a["published_date"] or datetime.min.date(), reverse=True)
        return all_articles

    def _fetch_feed(self, feed_config, cutoff, max_items):
        name = feed_config["name"]
        url = feed_config["url"]

        feed_type, feed = _parse_feed(url)
        if not feed:
            logger.warning(f"[{self.name}] Could not parse feed: {name}")
            return []

        articles = []
        items = feed.items if feed_type == "rss" else (feed.entries if hasattr(feed, 'entries') else [])

        for item in items[:max_items]:
            if feed_type == "rss":
                published = item.pub_date
                title = item.title or ""
                link = item.link or ""
                summary = item.description or ""
            else:
                published = item.published if hasattr(item, 'published') else (item.updated if hasattr(item, 'updated') else None)
                title = item.title.value if hasattr(item.title, 'value') else str(item.title or "")
                link = item.links[0].href if item.links else ""
                summary = item.summary.value if hasattr(item, 'summary') and item.summary and hasattr(item.summary, 'value') else ""

            if published:
                pub_naive = published.replace(tzinfo=None) if hasattr(published, 'tzinfo') and published.tzinfo else published
                if isinstance(pub_naive, datetime) and pub_naive < cutoff:
                    continue

            pub_date = published.date() if published and isinstance(published, datetime) else None

            articles.append({
                "title": title.strip(),
                "url": link,
                "published_date": pub_date,
                "source_name": name,
                "snippet": self._clean_snippet(summary),
            })

        logger.info(f"[{self.name}] Fetched {len(articles)} articles from {name}")
        return articles

    @staticmethod
    def _clean_snippet(text):
        """Remove HTML tags and truncate snippet."""
        clean = re.sub(r"<[^>]+>", "", text)
        clean = clean.strip()
        return clean[:500] if len(clean) > 500 else clean

    def match_articles_to_companies(self, articles, company_names):
        """Match news articles to companies by name mention in title or snippet."""
        matches = {}
        name_lower_map = {name.lower(): name for name in company_names}

        for article in articles:
            text = f"{article['title']} {article['snippet']}".lower()
            for name_lower, name in name_lower_map.items():
                if len(name_lower) >= 4 and name_lower in text:
                    if name not in matches:
                        matches[name] = []
                    matches[name].append(article)

        return matches
