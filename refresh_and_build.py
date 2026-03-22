#!/usr/bin/env python3
"""Refresh live data from free sources and rebuild the standalone index.html.

Usage:
    python3 refresh_and_build.py          # Full refresh: news + scores + rebuild HTML
    python3 refresh_and_build.py --quick   # Just rebuild HTML from current DB data
    python3 refresh_and_build.py --news    # Fetch news only, then rebuild

No API keys required — uses free RSS feeds (Google News, Sifted, Tech.eu, AltFi, Finextra).
"""

import sys
import json
import re
import logging
from datetime import datetime, date
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("refresh_and_build")

ROOT = Path(__file__).parent


class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


def fetch_live_news():
    """Fetch news from free RSS feeds and match to companies in the DB."""
    from database.db import init_db, get_session
    from database.models import Company, NewsArticle
    from scrapers.google_news import GoogleNewsScraper
    from scrapers.sifted_news import FintechNewsScraper

    init_db()
    session = get_session()

    companies = session.query(Company).all()
    company_names = [c.name for c in companies]
    total_added = 0

    # 1. Google News per company (top 50 by quality score)
    google = GoogleNewsScraper()
    top_companies = sorted(companies, key=lambda c: c.quality_score or 0, reverse=True)[:50]
    for company in top_companies:
        existing_urls = {a.url for a in company.news_articles}
        articles = google.fetch_news(company.name, max_articles=5)
        for a in articles:
            if a["url"] in existing_urls:
                continue
            session.add(NewsArticle(
                company_id=company.id,
                title=a["title"],
                url=a["url"],
                published_date=a.get("published_date"),
                source_name=a.get("source_name", ""),
                snippet=a.get("snippet", ""),
            ))
            total_added += 1

    # 2. Industry news feeds (Sifted, Tech.eu, AltFi, Finextra)
    fintech_news = FintechNewsScraper()
    industry_articles = fintech_news.fetch_all_feeds(max_age_days=30)
    matches = fintech_news.match_articles_to_companies(industry_articles, company_names)

    name_to_company = {c.name: c for c in companies}
    for name, articles in matches.items():
        company = name_to_company[name]
        existing_urls = {a.url for a in company.news_articles}
        for a in articles:
            if a["url"] in existing_urls:
                continue
            session.add(NewsArticle(
                company_id=company.id,
                title=a["title"],
                url=a["url"],
                published_date=a.get("published_date"),
                source_name=a.get("source_name", ""),
                snippet=a.get("snippet", ""),
            ))
            total_added += 1

    # 3. General fintech industry news (for discovery)
    general_news = google.fetch_fintech_industry_news(max_articles=30)
    logger.info(f"Fetched {len(general_news)} general fintech news articles for discovery")

    session.commit()
    session.close()
    logger.info(f"Added {total_added} new articles across all companies")
    return total_added


def run_scoring():
    """Re-score all companies."""
    from processors.scorer import CompanyScorer
    from processors.raise_predictor import RaisePredictor

    scorer = CompanyScorer()
    scorer.score_all()

    predictor = RaisePredictor()
    predictor.predict_all()
    logger.info("Scoring and predictions updated")


def build_html():
    """Export DB data and rebuild index.html with embedded company data."""
    from database.db import init_db, get_session
    from database.models import Company, FundingRound, NewsArticle

    init_db()
    session = get_session()

    companies = session.query(Company).order_by(Company.quality_score.desc()).all()
    data = []
    for c in companies:
        company_dict = {
            "name": c.name,
            "description": c.description or "",
            "website": c.website or "",
            "linkedin_url": c.linkedin_url or "",
            "hq_city": c.hq_city or "",
            "hq_country": c.hq_country or "",
            "category": c.category or "",
            "stage": c.stage or "",
            "founded_year": c.founded_year,
            "total_raised_usd": c.total_raised_usd or 0,
            "employee_count": c.employee_count or 0,
            "crunchbase_url": c.crunchbase_url or "",
            "quality_score": round(c.quality_score or 0, 1),
            "growth_signal": round(c.growth_signal or 0, 1),
            "next_raise_estimate": c.next_raise_estimate or "",
            "next_raise_confidence": c.next_raise_confidence or "",
            "last_round_date": c.last_round_date.isoformat() if c.last_round_date else None,
            "last_round_type": c.last_round_type or "",
            "last_round_size_usd": c.last_round_size_usd,
            "funding_rounds": [],
            "news_articles": [],
        }

        for fr in c.funding_rounds[:5]:
            company_dict["funding_rounds"].append({
                "round_type": fr.round_type,
                "announced_date": fr.announced_date.isoformat() if fr.announced_date else None,
                "amount_usd": fr.amount_usd,
                "lead_investors": fr.lead_investors,
                "all_investors": fr.all_investors,
            })

        for article in c.news_articles[:5]:
            company_dict["news_articles"].append({
                "title": article.title,
                "url": article.url,
                "published_date": article.published_date.isoformat() if article.published_date else None,
                "source_name": article.source_name,
            })

        data.append(company_dict)

    session.close()

    # Read index.html and replace the COMPANIES data
    html_path = ROOT / "index.html"
    html = html_path.read_text()

    old_match = re.search(r'const COMPANIES = \[.*?\];', html, re.DOTALL)
    if not old_match:
        logger.error("Could not find COMPANIES array in index.html")
        return

    new_data = 'const COMPANIES = ' + json.dumps(data, cls=DateEncoder, separators=(',', ':')) + ';'
    html = html[:old_match.start()] + new_data + html[old_match.end():]

    # Update the "last updated" timestamp if present
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    html = re.sub(
        r'id="last-updated">[^<]*<',
        f'id="last-updated">Last updated: {timestamp}<',
        html,
    )

    html_path.write_text(html)
    logger.info(f"Rebuilt index.html with {len(data)} companies (including news & scores)")


def main():
    args = sys.argv[1:]

    if "--quick" in args:
        logger.info("Quick rebuild — using existing DB data")
        build_html()
    elif "--news" in args:
        logger.info("Fetching live news...")
        fetch_live_news()
        run_scoring()
        build_html()
    else:
        logger.info("Full refresh — fetching news, scoring, rebuilding HTML")
        fetch_live_news()
        run_scoring()
        build_html()

    logger.info("Done! Open index.html in your browser.")


if __name__ == "__main__":
    main()
