"""APScheduler setup for daily data refresh jobs."""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import Config
from database.db import get_session
from database.models import ScanLog

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _log_job(job_name, func):
    """Wrapper to log job execution."""
    session = get_session()
    log = ScanLog(job_name=job_name)
    session.add(log)
    session.commit()

    try:
        result = func()
        log.status = "completed"
        log.completed_at = datetime.utcnow()
        if isinstance(result, int):
            log.articles_added = result
        session.commit()
        logger.info(f"Job '{job_name}' completed successfully")
    except Exception as e:
        log.status = "failed"
        log.error_msg = str(e)[:1000]
        log.completed_at = datetime.utcnow()
        session.commit()
        logger.error(f"Job '{job_name}' failed: {e}")
    finally:
        session.close()


def job_refresh_news():
    """Refresh news articles for all companies."""
    from processors.enricher import DataEnricher
    enricher = DataEnricher()
    return enricher.refresh_news_all()


def job_recalculate_scores():
    """Recalculate quality scores and raise predictions."""
    from processors.scorer import CompanyScorer
    from processors.raise_predictor import RaisePredictor

    scorer = CompanyScorer()
    scorer.score_all()

    predictor = RaisePredictor()
    predictor.predict_all()


def job_enrich_top_companies():
    """Enrich top 50 companies by quality score."""
    from processors.enricher import DataEnricher
    enricher = DataEnricher()
    enricher.enrich_all_companies(limit=50)


def init_scheduler(app):
    """Initialize and start the scheduler with daily jobs."""
    hour = Config.SCHEDULER_HOUR

    scheduler.add_job(
        lambda: _log_job("refresh_news", job_refresh_news),
        trigger=CronTrigger(hour=hour, minute=0),
        id="refresh_news",
        replace_existing=True,
    )

    scheduler.add_job(
        lambda: _log_job("enrich_top_companies", job_enrich_top_companies),
        trigger=CronTrigger(hour=hour, minute=30),
        id="enrich_top_companies",
        replace_existing=True,
    )

    scheduler.add_job(
        lambda: _log_job("recalculate_scores", job_recalculate_scores),
        trigger=CronTrigger(hour=hour + 1, minute=0),
        id="recalculate_scores",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"Scheduler started — daily jobs at {hour}:00 UTC")
