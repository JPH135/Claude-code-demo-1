"""Crunchbase API client — free tier (200 requests/month)."""

import logging
from datetime import datetime
from scrapers.base import BaseScraper
from config import Config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.crunchbase.com/api/v4"


class CrunchbaseScraper(BaseScraper):
    def __init__(self):
        super().__init__("crunchbase")
        self.api_key = Config.CRUNCHBASE_API_KEY
        self.enabled = bool(self.api_key)
        if not self.enabled:
            logger.info("Crunchbase API key not set — scraper disabled (set CRUNCHBASE_API_KEY)")

    def _params(self, extra=None):
        params = {"user_key": self.api_key}
        if extra:
            params.update(extra)
        return params

    def search_organizations(self, query, location=None, categories=None, limit=25):
        """Search for fintech companies."""
        if not self.enabled:
            return []

        params = self._params({
            "query": query,
            "collection_ids": "organizations",
            "limit": limit,
        })

        data = self.get_json(f"{BASE_URL}/autocompletes", params=params)
        if not data:
            return []

        results = []
        for entity in data.get("entities", []):
            props = entity.get("properties", {})
            results.append({
                "uuid": entity.get("uuid", ""),
                "name": props.get("value", ""),
                "permalink": props.get("permalink", ""),
                "short_description": props.get("short_description", ""),
                "entity_type": entity.get("facet_ids", []),
            })
        return results

    def get_organization(self, permalink):
        """Get detailed organization profile."""
        if not self.enabled:
            return None

        params = self._params({
            "field_ids": ",".join([
                "short_description", "description", "founded_on", "website_url",
                "linkedin", "num_employees_enum", "categories", "category_groups",
                "location_identifiers", "funding_total", "last_funding_type",
                "last_funding_at", "num_funding_rounds", "investor_identifiers",
            ]),
        })

        data = self.get_json(f"{BASE_URL}/entities/organizations/{permalink}", params=params)
        if not data:
            return None

        props = data.get("properties", {})
        cards = data.get("cards", {})

        # Parse location
        location_ids = props.get("location_identifiers", [])
        city = ""
        country = ""
        for loc in location_ids:
            loc_type = loc.get("location_type", "")
            if loc_type == "city":
                city = loc.get("value", "")
            elif loc_type == "country":
                country = loc.get("value", "")

        # Parse categories
        categories = props.get("categories", [])
        category = categories[0].get("value", "") if categories else ""

        # Parse employee range
        emp_enum = props.get("num_employees_enum", "")
        employee_estimate = self._parse_employee_range(emp_enum)

        return {
            "name": props.get("value", permalink),
            "description": props.get("short_description", ""),
            "full_description": props.get("description", ""),
            "website": props.get("website_url", ""),
            "linkedin_url": props.get("linkedin", {}).get("value", ""),
            "founded_year": self._parse_year(props.get("founded_on", "")),
            "category": category,
            "hq_city": city,
            "hq_country": country,
            "total_raised_usd": props.get("funding_total", {}).get("value_usd"),
            "last_funding_type": props.get("last_funding_type", ""),
            "last_funding_at": props.get("last_funding_at", ""),
            "employee_estimate": employee_estimate,
            "crunchbase_url": f"https://www.crunchbase.com/organization/{permalink}",
        }

    def get_funding_rounds(self, permalink):
        """Get funding rounds for an organization."""
        if not self.enabled:
            return []

        params = self._params({
            "field_ids": ",".join([
                "identifier", "announced_on", "money_raised",
                "investment_type", "lead_investor_identifiers",
                "investor_identifiers",
            ]),
            "limit": 20,
        })

        data = self.get_json(
            f"{BASE_URL}/entities/organizations/{permalink}/cards/funding_rounds",
            params=params,
        )
        if not data:
            return []

        rounds = []
        for item in data.get("cards", {}).get("funding_rounds", []):
            props = item.get("properties", {})

            lead_investors = [
                inv.get("value", "") for inv in props.get("lead_investor_identifiers", [])
            ]
            all_investors = [
                inv.get("value", "") for inv in props.get("investor_identifiers", [])
            ]

            rounds.append({
                "round_type": props.get("investment_type", ""),
                "announced_date": props.get("announced_on", ""),
                "amount_usd": props.get("money_raised", {}).get("value_usd"),
                "currency_original": props.get("money_raised", {}).get("currency", "USD"),
                "amount_original": props.get("money_raised", {}).get("value"),
                "lead_investors": lead_investors,
                "all_investors": all_investors,
            })
        return rounds

    @staticmethod
    def _parse_year(date_str):
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").year
        except ValueError:
            try:
                return int(date_str[:4])
            except (ValueError, TypeError):
                return None

    @staticmethod
    def _parse_employee_range(enum_val):
        """Convert Crunchbase employee enum to midpoint estimate."""
        mapping = {
            "c_00001_00010": 5,
            "c_00011_00050": 30,
            "c_00051_00100": 75,
            "c_00101_00250": 175,
            "c_00251_00500": 375,
            "c_00501_01000": 750,
            "c_01001_05000": 3000,
            "c_05001_10000": 7500,
            "c_10001_plus": 15000,
        }
        return mapping.get(enum_val)
