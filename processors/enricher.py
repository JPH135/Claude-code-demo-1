"""Data enrichment — merge and normalize data from multiple sources."""

import json
import logging
from datetime import datetime, date

from database.db import get_session
from database.models import Company, FundingRound, NewsArticle, EmployeeSnapshot
from scrapers.companies_house import CompaniesHouseScraper
from scrapers.google_news import GoogleNewsScraper
from scrapers.crunchbase import CrunchbaseScraper
from scrapers.linkedin_public import LinkedInScraper

logger = logging.getLogger(__name__)


class DataEnricher:
    """Enrich company records with data from external sources."""

    def __init__(self):
        self.ch_scraper = CompaniesHouseScraper()
        self.news_scraper = GoogleNewsScraper()
        self.cb_scraper = CrunchbaseScraper()
        self.li_scraper = LinkedInScraper()

    def enrich_company(self, company_id):
        """Run all available enrichment on a single company."""
        session = get_session()
        try:
            company = session.query(Company).get(company_id)
            if not company:
                logger.warning(f"Company {company_id} not found")
                return

            logger.info(f"Enriching: {company.name}")
            self._enrich_from_companies_house(session, company)
            self._enrich_from_crunchbase(session, company)
            self._enrich_from_linkedin(session, company)
            self._enrich_news(session, company)

            company.last_scraped_at = datetime.utcnow()
            company.updated_at = datetime.utcnow()
            session.commit()
            logger.info(f"Enrichment complete for {company.name}")
        except Exception as e:
            session.rollback()
            logger.error(f"Error enriching company {company_id}: {e}")
        finally:
            session.close()

    def enrich_all_companies(self, limit=None):
        """Enrich all companies in the database."""
        session = get_session()
        try:
            query = session.query(Company).order_by(Company.quality_score.desc())
            if limit:
                query = query.limit(limit)
            companies = query.all()
            company_ids = [c.id for c in companies]
        finally:
            session.close()

        for cid in company_ids:
            self.enrich_company(cid)

    def refresh_news_all(self):
        """Refresh news articles for all companies."""
        session = get_session()
        try:
            companies = session.query(Company).all()
            total_added = 0
            for company in companies:
                count = self._enrich_news(session, company)
                total_added += count
            session.commit()
            logger.info(f"News refresh complete: {total_added} new articles added")
            return total_added
        except Exception as e:
            session.rollback()
            logger.error(f"News refresh failed: {e}")
            return 0
        finally:
            session.close()

    def _enrich_from_companies_house(self, session, company):
        """Enrich with UK Companies House data."""
        if company.hq_country and company.hq_country != "United Kingdom":
            return

        data = self.ch_scraper.enrich_company(company.name, company.companies_house_id)
        if not data:
            return

        if data.get("companies_house_id"):
            company.companies_house_id = data["companies_house_id"]
        if data.get("founded_year") and not company.founded_year:
            company.founded_year = data["founded_year"]
        if data.get("hq_city") and not company.hq_city:
            company.hq_city = data["hq_city"]

    def _enrich_from_crunchbase(self, session, company):
        """Enrich with Crunchbase data."""
        if not self.cb_scraper.enabled:
            return

        # Search for the company
        permalink = company.crunchbase_url.rstrip("/").split("/")[-1] if company.crunchbase_url else None
        if not permalink:
            results = self.cb_scraper.search_organizations(company.name)
            if not results:
                return
            permalink = results[0].get("permalink", "")

        if not permalink:
            return

        # Get organization profile
        org = self.cb_scraper.get_organization(permalink)
        if not org:
            return

        # Update fields if empty
        if org.get("description") and not company.description:
            company.description = org["description"]
        if org.get("website") and not company.website:
            company.website = org["website"]
        if org.get("linkedin_url") and not company.linkedin_url:
            company.linkedin_url = org["linkedin_url"]
        if org.get("founded_year") and not company.founded_year:
            company.founded_year = org["founded_year"]
        if org.get("category") and not company.category:
            company.category = org["category"]
        if org.get("hq_city") and not company.hq_city:
            company.hq_city = org["hq_city"]
        if org.get("hq_country") and not company.hq_country:
            company.hq_country = org["hq_country"]
        if org.get("total_raised_usd"):
            company.total_raised_usd = org["total_raised_usd"]
        if org.get("employee_estimate") and not company.employee_count:
            company.employee_count = org["employee_estimate"]
        if not company.crunchbase_url:
            company.crunchbase_url = org.get("crunchbase_url", "")

        # Get funding rounds
        rounds = self.cb_scraper.get_funding_rounds(permalink)
        existing_dates = {r.announced_date for r in company.funding_rounds if r.announced_date}

        for round_data in rounds:
            announced = None
            if round_data.get("announced_date"):
                try:
                    announced = datetime.strptime(round_data["announced_date"], "%Y-%m-%d").date()
                except ValueError:
                    pass

            if announced and announced in existing_dates:
                continue

            fr = FundingRound(
                company_id=company.id,
                round_type=round_data.get("round_type", ""),
                announced_date=announced,
                amount_usd=round_data.get("amount_usd"),
                currency_original=round_data.get("currency_original", "USD"),
                amount_original=round_data.get("amount_original"),
                lead_investors_json=json.dumps(round_data.get("lead_investors", [])),
                all_investors_json=json.dumps(round_data.get("all_investors", [])),
            )
            session.add(fr)

        # Update last round info
        if rounds:
            latest = rounds[0]
            if latest.get("announced_date"):
                try:
                    company.last_round_date = datetime.strptime(latest["announced_date"], "%Y-%m-%d").date()
                except ValueError:
                    pass
            company.last_round_type = latest.get("round_type", "")
            company.last_round_size_usd = latest.get("amount_usd")
            # Infer stage from round type
            stage_map = {
                "seed": "Seed", "pre_seed": "Seed", "angel": "Seed",
                "series_a": "Series A", "series_b": "Series B",
                "series_c": "Series C", "series_d": "Series D",
                "series_e": "Growth", "series_f": "Growth",
                "private_equity": "Growth", "secondary_market": "Growth",
            }
            company.stage = stage_map.get(latest.get("round_type", "").lower(), company.stage)

    def _enrich_from_linkedin(self, session, company):
        """Enrich with LinkedIn employee count."""
        if not company.linkedin_url:
            return

        data = self.li_scraper.get_employee_count(company.linkedin_url)
        if not data:
            return

        new_count = data["employee_count"]

        # Calculate growth if we have previous snapshots
        if company.employee_count and company.employee_count > 0:
            growth = ((new_count - company.employee_count) / company.employee_count) * 100
            company.employee_growth_6m = round(growth, 1)

        company.employee_count = new_count
        company.employee_count_updated = datetime.utcnow()

        # Save snapshot
        snapshot = EmployeeSnapshot(
            company_id=company.id,
            employee_count=new_count,
            snapshot_date=date.today(),
            source=data.get("source", "linkedin"),
        )
        session.add(snapshot)

    def _enrich_news(self, session, company):
        """Fetch and store recent news articles."""
        articles = self.news_scraper.fetch_news(company.name)
        if not articles:
            return 0

        existing_urls = {a.url for a in company.news_articles}
        added = 0

        for article_data in articles:
            if article_data["url"] in existing_urls:
                continue

            article = NewsArticle(
                company_id=company.id,
                title=article_data["title"],
                url=article_data["url"],
                published_date=article_data.get("published_date"),
                source_name=article_data.get("source_name", ""),
                snippet=article_data.get("snippet", ""),
            )
            session.add(article)
            added += 1

        return added
