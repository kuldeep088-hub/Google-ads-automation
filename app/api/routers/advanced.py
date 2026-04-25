import json
import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import (
    NegativeKeywordAdded, PromotedKeyword, QualityScoreHistory, MLBidPrediction,
)

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

MICROS = 1_000_000


@router.get("/negative-keywords", response_class=HTMLResponse)
async def negative_keywords_page(request: Request, db: Session = Depends(get_db)):
    rows = (
        db.query(NegativeKeywordAdded)
        .order_by(NegativeKeywordAdded.added_at.desc())
        .limit(200)
        .all()
    )
    total_wasted_usd = sum(r.cost_wasted_micros / MICROS for r in rows)
    return templates.TemplateResponse(
        "advanced/negative_keywords.html",
        {"request": request, "rows": rows, "total_wasted_usd": round(total_wasted_usd, 2)},
    )


@router.get("/promoted-keywords", response_class=HTMLResponse)
async def promoted_keywords_page(request: Request, db: Session = Depends(get_db)):
    rows = (
        db.query(PromotedKeyword)
        .order_by(PromotedKeyword.promoted_at.desc())
        .limit(200)
        .all()
    )
    return templates.TemplateResponse(
        "advanced/promoted_keywords.html",
        {"request": request, "rows": rows},
    )


@router.get("/quality-scores", response_class=HTMLResponse)
async def quality_scores_page(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    rows = (
        db.query(QualityScoreHistory)
        .filter(QualityScoreHistory.snapshot_date == today)
        .order_by(QualityScoreHistory.quality_score.asc())
        .all()
    )
    if not rows:
        # fall back to latest available date
        rows = (
            db.query(QualityScoreHistory)
            .order_by(QualityScoreHistory.snapshot_date.desc(), QualityScoreHistory.quality_score.asc())
            .limit(200)
            .all()
        )

    qs_distribution = [0] * 11  # index 0..10
    for r in rows:
        if r.quality_score is not None:
            qs_distribution[min(r.quality_score, 10)] += 1

    chart_labels = json.dumps([str(i) for i in range(11)])
    chart_data = json.dumps(qs_distribution)

    return templates.TemplateResponse(
        "advanced/quality_scores.html",
        {
            "request": request,
            "rows": rows,
            "chart_labels": chart_labels,
            "chart_data": chart_data,
            "snapshot_date": today.strftime("%Y-%m-%d"),
        },
    )


@router.get("/ml-predictions", response_class=HTMLResponse)
async def ml_predictions_page(request: Request, db: Session = Depends(get_db)):
    rows = (
        db.query(MLBidPrediction)
        .order_by(MLBidPrediction.created_at.desc())
        .limit(200)
        .all()
    )
    # Compute bid change direction for display
    enriched = []
    for r in rows:
        delta = r.predicted_bid_micros - r.current_bid_micros
        delta_pct = round(delta / max(r.current_bid_micros, 1) * 100, 1)
        enriched.append({
            "row": r,
            "delta_pct": delta_pct,
            "direction": "up" if delta > 0 else ("down" if delta < 0 else "flat"),
        })

    return templates.TemplateResponse(
        "advanced/ml_predictions.html",
        {"request": request, "enriched": enriched},
    )
