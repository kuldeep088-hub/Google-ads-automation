import json
import logging
from datetime import datetime

from app.database import SessionLocal
from app.db.models import JobRun, MLBidPrediction, QualityScoreHistory

logger = logging.getLogger(__name__)
MICROS = 1_000_000
APPLY_PREDICTIONS = False  # set True to auto-apply bids; False = store for review


def run_ml_bid_optimization(triggered_by: str = "scheduler"):
    db = SessionLocal()
    job_run = JobRun(
        job_name="ml_bid_optimization",
        status="running",
        started_at=datetime.utcnow(),
        triggered_by=triggered_by,
    )
    db.add(job_run)
    db.commit()

    actions_taken = 0

    try:
        from app.ml.bid_predictor import train_model, predict_optimal_bid

        # Retrain model with latest data (no-op if too few samples)
        train_model(db)

        # Pull current keyword data for prediction
        from app.google_ads.quality_score_service import QualityScoreService
        svc = QualityScoreService()
        keywords = svc.get_all_keyword_quality_scores()

        for kw in keywords:
            row = {
                "clicks": kw.get("clicks", 0),
                "impressions": kw.get("impressions", 0),
                "conversions": kw.get("conversions", 0),
                "cost_micros": kw.get("cost_micros", 0),
                "cpc_bid_micros": kw.get("cpc_bid_micros", 500_000),
                "match_type": kw.get("match_type", "BROAD"),
            }
            result = predict_optimal_bid(row)
            predicted = result["predicted_bid_micros"]
            current = kw.get("cpc_bid_micros", 0)

            db.merge(MLBidPrediction(
                criterion_resource=kw["criterion_resource"],
                keyword_text=kw.get("keyword_text", ""),
                campaign_name=kw.get("campaign_name"),
                current_bid_micros=current,
                predicted_bid_micros=predicted,
                predicted_cpa=result["predicted_cpa"],
                confidence=result["confidence"],
                action_taken=None,
                model_version=result["method"],
            ))

            if APPLY_PREDICTIONS and result["confidence"] >= 0.75:
                from app.google_ads.bid_service import BidService
                applied = BidService().update_keyword_bid(kw["criterion_resource"], predicted)
                if applied:
                    actions_taken += 1

        db.commit()
        job_run.status = "success"
        job_run.actions_taken = actions_taken
        job_run.rules_evaluated = len(keywords)
        logger.info(
            "ML bid optimization: %d keywords scored, %d bids applied",
            len(keywords), actions_taken,
        )

    except Exception as exc:
        db.rollback()
        job_run.status = "failed"
        job_run.errors_count = 1
        job_run.error_summary = json.dumps([str(exc)])
        logger.exception("ml_bid_optimization job failed")
        _send_failure_alert("ml_bid_optimization", str(exc))
    finally:
        job_run.finished_at = datetime.utcnow()
        db.commit()
        db.close()


def _send_failure_alert(job_name: str, error: str):
    try:
        from app.notifications.slack_sender import SlackSender
        SlackSender().send(f":red_circle: *{job_name}* job failed: {error}")
    except Exception:
        pass
