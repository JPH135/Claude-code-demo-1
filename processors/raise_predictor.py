"""Next fundraise timing prediction model."""

import logging
from datetime import datetime, timedelta

from database.db import get_session
from database.models import Company

logger = logging.getLogger(__name__)

# Median months between rounds (based on industry data)
STAGE_INTERVALS = {
    "Seed": {"next": "Series A", "median_months": 18, "range": (12, 30)},
    "Series A": {"next": "Series B", "median_months": 24, "range": (15, 36)},
    "Series B": {"next": "Series C", "median_months": 24, "range": (18, 36)},
    "Series C": {"next": "Series D", "median_months": 30, "range": (24, 48)},
    "Series D": {"next": "Growth", "median_months": 36, "range": (24, 60)},
    "Growth": {"next": "Growth/IPO", "median_months": 36, "range": (24, 60)},
}


class RaisePredictor:
    """Predict when a company is likely to raise its next funding round."""

    def predict_all(self):
        """Update raise predictions for all companies."""
        session = get_session()
        try:
            companies = session.query(Company).filter(Company.last_round_date.isnot(None)).all()
            for company in companies:
                self._predict(company)
            session.commit()
            logger.info(f"Updated raise predictions for {len(companies)} companies")
        except Exception as e:
            session.rollback()
            logger.error(f"Raise prediction failed: {e}")
        finally:
            session.close()

    def predict_company(self, company_id):
        """Update raise prediction for a single company."""
        session = get_session()
        try:
            company = session.query(Company).get(company_id)
            if company and company.last_round_date:
                self._predict(company)
                session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Prediction failed for {company_id}: {e}")
        finally:
            session.close()

    def _predict(self, company):
        """Core prediction logic."""
        if not company.last_round_date:
            company.next_raise_estimate = "Unknown"
            company.next_raise_confidence = "Low"
            return

        stage = company.stage or ""
        interval = STAGE_INTERVALS.get(stage)

        if not interval:
            # Default if stage unknown
            median_months = 24
            range_low, range_high = 18, 36
        else:
            median_months = interval["median_months"]
            range_low, range_high = interval["range"]

        # Apply modifiers based on growth signals
        modifier = 0

        # Fast employee growth → likely to raise sooner
        if company.employee_growth_6m:
            if company.employee_growth_6m >= 50:
                modifier -= 4  # 4 months sooner
            elif company.employee_growth_6m >= 25:
                modifier -= 2

        # Recent heavy news activity → might be preparing to raise
        if company.news_articles:
            recent_count = sum(
                1 for a in company.news_articles
                if a.published_date and (datetime.utcnow().date() - a.published_date).days <= 30
            )
            if recent_count >= 5:
                modifier -= 3

        # Large last round → can go longer
        if company.last_round_size_usd and company.last_round_size_usd >= 100_000_000:
            modifier += 6

        adjusted_months = max(6, median_months + modifier)
        estimated_date = company.last_round_date + timedelta(days=adjusted_months * 30)
        months_since = (datetime.utcnow().date() - company.last_round_date).days / 30

        # Format the prediction
        now = datetime.utcnow().date()

        if estimated_date < now:
            months_overdue = (now - estimated_date).days / 30
            if months_overdue > 12:
                company.next_raise_estimate = "Significantly overdue"
                company.next_raise_confidence = "High"
            elif months_overdue > 6:
                company.next_raise_estimate = "Overdue — likely raising now"
                company.next_raise_confidence = "High"
            else:
                company.next_raise_estimate = "Approaching — imminent"
                company.next_raise_confidence = "Medium"
        else:
            months_until = (estimated_date - now).days / 30
            quarter = f"Q{(estimated_date.month - 1) // 3 + 1} {estimated_date.year}"

            if months_until <= 6:
                company.next_raise_estimate = f"{quarter} (soon)"
                company.next_raise_confidence = "High"
            elif months_until <= 12:
                company.next_raise_estimate = f"{quarter} (likely)"
                company.next_raise_confidence = "Medium"
            elif months_until <= 18:
                company.next_raise_estimate = f"~{estimated_date.year}"
                company.next_raise_confidence = "Medium"
            else:
                company.next_raise_estimate = f"{estimated_date.year}+"
                company.next_raise_confidence = "Low"

    @staticmethod
    def get_stage_context(stage):
        """Return human-readable context about typical raise timing for a stage."""
        interval = STAGE_INTERVALS.get(stage)
        if not interval:
            return "No benchmark data available for this stage."

        return (
            f"Companies at {stage} typically raise their {interval['next']} "
            f"round after {interval['median_months']} months "
            f"(range: {interval['range'][0]}–{interval['range'][1]} months)."
        )
