"""Quality scoring and growth signal computation for companies."""

import logging
from datetime import datetime, timedelta

from database.db import get_session
from database.models import Company
from config import Config

logger = logging.getLogger(__name__)


class CompanyScorer:
    """Compute quality scores and growth signals for companies."""

    def score_all(self):
        """Recalculate scores for all companies."""
        session = get_session()
        try:
            companies = session.query(Company).all()
            for company in companies:
                self._score_company(company)
            session.commit()
            logger.info(f"Scored {len(companies)} companies")
        except Exception as e:
            session.rollback()
            logger.error(f"Scoring failed: {e}")
        finally:
            session.close()

    def score_company(self, company_id):
        """Recalculate score for a single company."""
        session = get_session()
        try:
            company = session.query(Company).get(company_id)
            if company:
                self._score_company(company)
                session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Scoring failed for company {company_id}: {e}")
        finally:
            session.close()

    def _score_company(self, company):
        """Compute quality score (0-100) from multiple signals."""
        score = 0.0

        # 1. Investor tier score (0-20)
        score += self._investor_tier_score(company)

        # 2. Funding velocity (0-20)
        score += self._funding_velocity_score(company)

        # 3. Employee growth (0-20)
        score += self._employee_growth_score(company)

        # 4. News activity (0-15)
        score += self._news_activity_score(company)

        # 5. Revenue signals (0-15)
        score += self._revenue_signal_score(company)

        # 6. Stage premium (0-10)
        score += self._stage_score(company)

        company.quality_score = round(min(score, 100), 1)

        # Growth signal — separate metric
        company.growth_signal = round(self._compute_growth_signal(company), 1)

    def _investor_tier_score(self, company):
        """Score based on presence of tier-1 investors (0-20)."""
        tier1 = set(name.lower() for name in Config.TIER1_INVESTORS)
        investor_names = set()

        for fr in company.funding_rounds:
            for inv in fr.lead_investors:
                investor_names.add(inv.lower())
            for inv in fr.all_investors:
                investor_names.add(inv.lower())

        matches = investor_names & tier1
        if not matches:
            return 0

        # Lead investor gets more weight
        lead_matches = 0
        for fr in company.funding_rounds:
            for inv in fr.lead_investors:
                if inv.lower() in tier1:
                    lead_matches += 1

        return min(20, lead_matches * 8 + len(matches) * 3)

    def _funding_velocity_score(self, company):
        """Score based on funding amount relative to company age (0-20)."""
        if not company.total_raised_usd or not company.founded_year:
            return 0

        years_active = max(1, datetime.utcnow().year - company.founded_year)
        velocity = company.total_raised_usd / years_active / 1_000_000  # $M/year

        if velocity >= 50:
            return 20
        elif velocity >= 20:
            return 16
        elif velocity >= 10:
            return 12
        elif velocity >= 5:
            return 8
        elif velocity >= 1:
            return 4
        return 2

    def _employee_growth_score(self, company):
        """Score based on employee headcount growth (0-20)."""
        if not company.employee_growth_6m:
            # If we have employee count but no growth data, give baseline
            if company.employee_count:
                if company.employee_count >= 500:
                    return 10
                elif company.employee_count >= 100:
                    return 7
                elif company.employee_count >= 50:
                    return 5
                return 3
            return 0

        growth = company.employee_growth_6m
        if growth >= 100:
            return 20
        elif growth >= 50:
            return 16
        elif growth >= 30:
            return 12
        elif growth >= 15:
            return 8
        elif growth >= 5:
            return 4
        elif growth >= 0:
            return 2
        return 0  # Negative growth

    def _news_activity_score(self, company):
        """Score based on recent news mentions (0-15)."""
        if not company.news_articles:
            return 0

        cutoff_30d = (datetime.utcnow() - timedelta(days=30)).date()
        cutoff_90d = (datetime.utcnow() - timedelta(days=90)).date()

        recent_30 = sum(1 for a in company.news_articles if a.published_date and a.published_date >= cutoff_30d)
        recent_90 = sum(1 for a in company.news_articles if a.published_date and a.published_date >= cutoff_90d)

        score = 0
        if recent_30 >= 5:
            score = 15
        elif recent_30 >= 3:
            score = 12
        elif recent_30 >= 1:
            score = 8
        elif recent_90 >= 3:
            score = 5
        elif recent_90 >= 1:
            score = 3
        return score

    def _revenue_signal_score(self, company):
        """Score based on revenue data availability (0-15)."""
        if not company.revenue_estimate_usd:
            return 0

        rev = company.revenue_estimate_usd
        if rev >= 100_000_000:
            return 15
        elif rev >= 50_000_000:
            return 12
        elif rev >= 10_000_000:
            return 10
        elif rev >= 1_000_000:
            return 7
        return 3

    def _stage_score(self, company):
        """Score premium for growth-stage companies (0-10)."""
        stage_scores = {
            "Series A": 6,
            "Series B": 8,
            "Series C": 10,
            "Series D": 9,
            "Growth": 7,
            "Seed": 3,
        }
        return stage_scores.get(company.stage, 2)

    def _compute_growth_signal(self, company):
        """Compute growth signal (0-100) — a separate, faster-moving metric."""
        signal = 0.0

        # Employee growth momentum
        if company.employee_growth_6m:
            if company.employee_growth_6m >= 50:
                signal += 30
            elif company.employee_growth_6m >= 25:
                signal += 20
            elif company.employee_growth_6m >= 10:
                signal += 10

        # Recent funding
        if company.last_round_date:
            months_since = (datetime.utcnow().date() - company.last_round_date).days / 30
            if months_since <= 6:
                signal += 25
            elif months_since <= 12:
                signal += 15
            elif months_since <= 24:
                signal += 5

        # News momentum
        cutoff = (datetime.utcnow() - timedelta(days=30)).date()
        recent_news = sum(1 for a in company.news_articles if a.published_date and a.published_date >= cutoff)
        signal += min(20, recent_news * 5)

        # Raise overdue signal (might be looking for capital)
        if company.last_round_date:
            months_since = (datetime.utcnow().date() - company.last_round_date).days / 30
            if months_since >= 24:
                signal += 15

        # High absolute scale
        if company.employee_count and company.employee_count >= 200:
            signal += 10

        return min(signal, 100)
