import json
import logging
from datetime import datetime

from app.database import SessionLocal
from app.db.models import JobRun
from app.automation.rule_engine import RuleEngine

logger = logging.getLogger(__name__)


def _run_bid_rules(rule_types: list[str], job_name: str, triggered_by: str = "scheduler"):
    db = SessionLocal()
    job_run = JobRun(
        job_name=job_name,
        status="running",
        started_at=datetime.utcnow(),
        triggered_by=triggered_by,
    )
    db.add(job_run)
    db.commit()

    try:
        engine = RuleEngine(db=db)
        result = engine.run(rule_types[0])
        for rt in rule_types[1:]:
            result += engine.run(rt)

        job_run.status = "success"
        job_run.rules_evaluated = result.rules_evaluated
        job_run.actions_taken = result.actions_taken
        job_run.errors_count = result.errors_count
        logger.info(
            "%s completed: %d rules evaluated, %d actions taken",
            job_name, result.rules_evaluated, result.actions_taken,
        )
    except Exception as exc:
        job_run.status = "failed"
        job_run.errors_count = 1
        job_run.error_summary = json.dumps([str(exc)])
        logger.exception("%s job failed", job_name)
        _send_failure_alert(job_name, str(exc))
    finally:
        job_run.finished_at = datetime.utcnow()
        db.commit()
        db.close()


def run_bid_management(triggered_by: str = "scheduler"):
    _run_bid_rules(["cpa_bid", "device_bid", "keyword_performance_bid"], "bid_management", triggered_by)


def run_tod_bid_rules(triggered_by: str = "scheduler"):
    _run_bid_rules(["tod_bid"], "tod_bid_rules", triggered_by)


def _send_failure_alert(job_name: str, error: str):
    try:
        from app.notifications.slack_sender import SlackSender
        SlackSender().send(f":red_circle: *{job_name}* job failed: {error}")
    except Exception:
        pass
