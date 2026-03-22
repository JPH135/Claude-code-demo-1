"""Companies House API client — completely free UK company data."""

import logging
from datetime import datetime
from scrapers.base import BaseScraper
from config import Config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.company-information.service.gov.uk"


class CompaniesHouseScraper(BaseScraper):
    def __init__(self):
        super().__init__("companies_house")
        api_key = Config.COMPANIES_HOUSE_API_KEY
        if api_key:
            self.session.auth = (api_key, "")
            self.enabled = True
        else:
            self.enabled = False
            logger.info("Companies House API key not set — scraper disabled")

    def search_company(self, name):
        if not self.enabled:
            return []
        data = self.get_json(f"{BASE_URL}/search/companies", params={
            "q": name,
            "items_per_page": 5,
        })
        if not data:
            return []
        results = []
        for item in data.get("items", []):
            results.append({
                "company_number": item.get("company_number", ""),
                "title": item.get("title", ""),
                "company_status": item.get("company_status", ""),
                "date_of_creation": item.get("date_of_creation", ""),
                "address": item.get("address_snippet", ""),
                "company_type": item.get("company_type", ""),
            })
        return results

    def get_company_profile(self, company_number):
        if not self.enabled:
            return None
        data = self.get_json(f"{BASE_URL}/company/{company_number}")
        if not data:
            return None
        return {
            "company_number": data.get("company_number", ""),
            "company_name": data.get("company_name", ""),
            "status": data.get("company_status", ""),
            "type": data.get("type", ""),
            "date_of_creation": data.get("date_of_creation", ""),
            "registered_office": data.get("registered_office_address", {}),
            "sic_codes": data.get("sic_codes", []),
            "accounts": data.get("accounts", {}),
            "confirmation_statement": data.get("confirmation_statement", {}),
        }

    def get_officers(self, company_number):
        if not self.enabled:
            return []
        data = self.get_json(f"{BASE_URL}/company/{company_number}/officers")
        if not data:
            return []
        officers = []
        for item in data.get("items", []):
            if item.get("resigned_on"):
                continue
            officers.append({
                "name": item.get("name", ""),
                "role": item.get("officer_role", ""),
                "appointed_on": item.get("appointed_on", ""),
                "nationality": item.get("nationality", ""),
            })
        return officers

    def get_filing_history(self, company_number, items_per_page=10):
        if not self.enabled:
            return []
        data = self.get_json(
            f"{BASE_URL}/company/{company_number}/filing-history",
            params={"items_per_page": items_per_page},
        )
        if not data:
            return []
        filings = []
        for item in data.get("items", []):
            filings.append({
                "date": item.get("date", ""),
                "type": item.get("type", ""),
                "description": item.get("description", ""),
                "category": item.get("category", ""),
            })
        return filings

    def enrich_company(self, company_name, existing_ch_id=None):
        """Enrich a company with Companies House data. Returns dict of enrichments."""
        if not self.enabled:
            return {}

        company_number = existing_ch_id
        if not company_number:
            results = self.search_company(company_name)
            if not results:
                return {}
            # Take the first active result
            for r in results:
                if r["company_status"] == "active":
                    company_number = r["company_number"]
                    break
            if not company_number and results:
                company_number = results[0]["company_number"]

        profile = self.get_company_profile(company_number)
        if not profile:
            return {}

        enrichment = {
            "companies_house_id": company_number,
        }

        # Extract founding year
        creation_date = profile.get("date_of_creation", "")
        if creation_date:
            try:
                enrichment["founded_year"] = datetime.strptime(creation_date, "%Y-%m-%d").year
            except ValueError:
                pass

        # Extract address
        address = profile.get("registered_office", {})
        if address:
            locality = address.get("locality", "")
            if locality:
                enrichment["hq_city"] = locality

        return enrichment
