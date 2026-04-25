import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from app.config import settings

logger = logging.getLogger(__name__)


def create_scheduler() -> BackgroundScheduler:
    jobstores = {"default": SQLAlchemyJobStore(url=settings.DATABASE_URL)}
    executors = {"default": ThreadPoolExecutor(max_workers=4)}
    scheduler = BackgroundScheduler(
        jobstores=jobstores,
        executors=executors,
        timezone="UTC",
    )
    return scheduler


def register_jobs(scheduler: BackgroundScheduler) -> None:
    from app.jobs.bid_job import run_bid_management, run_tod_bid_rules
    from app.jobs.budget_job import run_budget_management
    from app.jobs.report_job import run_daily_reporting, run_weekly_reporting
    from app.jobs.negative_keywords_job import run_negative_keyword_mining
    from app.jobs.keyword_promotion_job import run_keyword_promotion
    from app.jobs.ml_bid_job import run_ml_bid_optimization
    from app.jobs.quality_score_job import run_quality_score_monitor

    scheduler.add_job(
        run_bid_management,
        trigger="cron",
        hour="*/1",
        id="bid_management",
        replace_existing=True,
        misfire_grace_time=600,
    )
    scheduler.add_job(
        run_tod_bid_rules,
        trigger="cron",
        minute="*/15",
        id="tod_bid_rules",
        replace_existing=True,
        misfire_grace_time=120,
    )
    scheduler.add_job(
        run_budget_management,
        trigger="cron",
        hour="*/2",
        id="budget_management",
        replace_existing=True,
        misfire_grace_time=600,
    )
    scheduler.add_job(
        run_daily_reporting,
        trigger="cron",
        hour=6,
        minute=0,
        id="daily_reporting",
        replace_existing=True,
    )
    scheduler.add_job(
        run_weekly_reporting,
        trigger="cron",
        day_of_week="mon",
        hour=7,
        id="weekly_reporting",
        replace_existing=True,
    )
    # Advanced features
    scheduler.add_job(
        run_negative_keyword_mining,
        trigger="cron",
        hour=4,
        minute=0,
        id="negative_keyword_mining",
        replace_existing=True,
        misfire_grace_time=600,
    )
    scheduler.add_job(
        run_keyword_promotion,
        trigger="cron",
        hour=4,
        minute=30,
        id="keyword_promotion",
        replace_existing=True,
        misfire_grace_time=600,
    )
    scheduler.add_job(
        run_ml_bid_optimization,
        trigger="cron",
        hour="*/3",
        id="ml_bid_optimization",
        replace_existing=True,
        misfire_grace_time=600,
    )
    scheduler.add_job(
        run_quality_score_monitor,
        trigger="cron",
        hour=5,
        minute=0,
        id="quality_score_monitor",
        replace_existing=True,
        misfire_grace_time=600,
    )
    logger.info("All automation jobs registered.")
