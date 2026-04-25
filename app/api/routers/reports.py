import json
import logging
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import ReportCache

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/daily", response_class=HTMLResponse)
async def daily_report(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    cached = (
        db.query(ReportCache)
        .filter(ReportCache.report_type == "daily_summary", ReportCache.report_date == today)
        .first()
    )
    data = json.loads(cached.payload) if cached else {}
    summary = data.get("summary", {})
    campaigns = data.get("campaigns", [])
    anomalies = data.get("anomalies", [])

    chart_labels = [c["campaign_name"] for c in campaigns[:10]]
    chart_cost = [round(c["cost_usd"], 2) for c in campaigns[:10]]
    chart_clicks = [c["clicks"] for c in campaigns[:10]]

    return templates.TemplateResponse(
        "reports/daily.html",
        {
            "request": request,
            "summary": summary,
            "campaigns": campaigns,
            "anomalies": anomalies,
            "report_date": today.strftime("%Y-%m-%d"),
            "chart_labels": json.dumps(chart_labels),
            "chart_cost": json.dumps(chart_cost),
            "chart_clicks": json.dumps(chart_clicks),
        },
    )


@router.get("/weekly", response_class=HTMLResponse)
async def weekly_report(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    cached = (
        db.query(ReportCache)
        .filter(ReportCache.report_type == "weekly_summary")
        .order_by(ReportCache.report_date.desc())
        .first()
    )
    data = json.loads(cached.payload) if cached else {}
    campaigns = data.get("campaigns", [])
    keywords = data.get("keywords", [])

    chart_labels = [c["campaign_name"] for c in campaigns[:10]]
    chart_cost = [round(c["cost_usd"], 2) for c in campaigns[:10]]
    chart_conversions = [round(c["conversions"], 1) for c in campaigns[:10]]

    return templates.TemplateResponse(
        "reports/weekly.html",
        {
            "request": request,
            "campaigns": campaigns,
            "keywords": keywords[:20],
            "chart_labels": json.dumps(chart_labels),
            "chart_cost": json.dumps(chart_cost),
            "chart_conversions": json.dumps(chart_conversions),
        },
    )


@router.get("/api/summary")
async def api_summary():
    try:
        from app.google_ads.report_service import ReportService
        svc = ReportService()
        return svc.get_daily_summary()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
