#!/usr/bin/env python3
"""CLI tool to seed database and run data refresh."""

import sys
import json
import re
import logging
from datetime import datetime, date
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("run_refresh")


def slugify(name):
    """Convert company name to URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def seed_database():
    """Load companies from seed_companies.json into the database."""
    from database.db import init_db, get_session
    from database.models import Company, FundingRound

    init_db()
    session = get_session()

    seed_file = Path(__file__).parent / "data" / "seed_companies.json"
    if not seed_file.exists():
        logger.error(f"Seed file not found: {seed_file}")
        return

    with open(seed_file) as f:
        companies_data = json.load(f)

    existing_slugs = {c[0] for c in session.query(Company.slug).all()}
    added = 0

    for data in companies_data:
        slug = slugify(data["name"])
        if slug in existing_slugs:
            continue

        company = Company(
            name=data["name"],
            slug=slug,
            description=data.get("description", ""),
            website=data.get("website", ""),
            linkedin_url=data.get("linkedin_url", ""),
            hq_city=data.get("hq_city", ""),
            hq_country=data.get("hq_country", ""),
            category=data.get("category", ""),
            stage=data.get("stage", ""),
            founded_year=data.get("founded_year"),
            total_raised_usd=data.get("total_raised_usd"),
            employee_count=data.get("employee_count"),
            crunchbase_url=data.get("crunchbase_url", ""),
        )
        session.add(company)
        existing_slugs.add(slug)
        added += 1

        # Add funding rounds if provided
        for round_data in data.get("funding_rounds", []):
            announced = None
            if round_data.get("announced_date"):
                try:
                    announced = datetime.strptime(round_data["announced_date"], "%Y-%m-%d").date()
                except ValueError:
                    pass

            fr = FundingRound(
                company=company,
                round_type=round_data.get("round_type", ""),
                announced_date=announced,
                amount_usd=round_data.get("amount_usd"),
                lead_investors_json=json.dumps(round_data.get("lead_investors", [])),
                all_investors_json=json.dumps(round_data.get("all_investors", [])),
            )
            session.add(fr)

            # Update company last round info
            if announced:
                if not company.last_round_date or announced > company.last_round_date:
                    company.last_round_date = announced
                    company.last_round_type = round_data.get("round_type", "")
                    company.last_round_size_usd = round_data.get("amount_usd")

    session.commit()
    session.close()
    logger.info(f"Seeded {added} companies (skipped {len(companies_data) - added} duplicates)")


def run_scoring():
    """Run quality scoring and raise prediction on all companies."""
    from processors.scorer import CompanyScorer
    from processors.raise_predictor import RaisePredictor

    logger.info("Running quality scoring...")
    scorer = CompanyScorer()
    scorer.score_all()

    logger.info("Running raise predictions...")
    predictor = RaisePredictor()
    predictor.predict_all()


def run_news_refresh():
    """Refresh news for all companies."""
    from processors.enricher import DataEnricher
    enricher = DataEnricher()
    enricher.refresh_news_all()


def run_full_enrichment(limit=None):
    """Run full enrichment on all companies."""
    from processors.enricher import DataEnricher
    enricher = DataEnricher()
    enricher.enrich_all_companies(limit=limit)


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_refresh.py <command>")
        print()
        print("Commands:")
        print("  seed         Load companies from seed_companies.json")
        print("  score        Run quality scoring and raise predictions")
        print("  news         Refresh news articles for all companies")
        print("  enrich       Full enrichment (Companies House, Crunchbase, LinkedIn, news)")
        print("  enrich --limit N  Enrich top N companies only")
        print("  all          Seed + score (quick start)")
        return

    command = sys.argv[1]

    if command == "seed":
        seed_database()
    elif command == "score":
        run_scoring()
    elif command == "news":
        run_news_refresh()
    elif command == "enrich":
        limit = None
        if "--limit" in sys.argv:
            idx = sys.argv.index("--limit")
            if idx + 1 < len(sys.argv):
                limit = int(sys.argv[idx + 1])
        run_full_enrichment(limit=limit)
    elif command == "all":
        seed_database()
        run_scoring()
        logger.info("Quick start complete! Run 'flask run' to start the dashboard.")
    else:
        print(f"Unknown command: {command}")
        main()


if __name__ == "__main__":
    main()
