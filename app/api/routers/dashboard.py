import json
import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import JobRun, PerformanceSnapshot

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _safe_ads_data(fn):
    try:
        return fn()
    except Exception as e:
        logger.warning("Ads API call failed (showing cached data): %s", e)
        return []


@router.get("/", response_class=HTMLResponse)
async def dashboard_index(request: Request, db: Session = Depends(get_db)):
    from app.google_ads.report_service import ReportService

    summary = {}
    campaigns = []
    chart_labels = []
    chart_cost = []
    chart_clicks = []
    chart_conversions = []

    try:
        svc = ReportService()
        summary = svc.get_daily_summary()
        campaigns = svc.get_campaign_performance("LAST_7_DAYS")
    except Exception as e:
        logger.warning("Dashboard data fetch failed: %s", e)

    # Build 7-day trend from snapshots
    for i in range(6, -1, -1):
        d = date.today() - timedelta(days=i)
        snap = (
            db.query(PerformanceSnapshot)
            .filter(
                PerformanceSnapshot.snapshot_date == d,
                PerformanceSnapshot.entity_type == "account",
            )
            .first()
        )
        chart_labels.append(d.strftime("%b %d"))
        chart_cost.append(round((snap.cost_micros / 1_000_000) if snap else 0, 2))
        chart_clicks.append(snap.clicks if snap else 0)
        chart_conversions.append(round(snap.conversions if snap else 0, 1))

    recent_jobs = db.query(JobRun).order_by(JobRun.started_at.desc()).limit(5).all()

    return templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "summary": summary,
            "campaigns": campaigns[:10],
            "recent_jobs": recent_jobs,
            "chart_labels": json.dumps(chart_labels),
            "chart_cost": json.dumps(chart_cost),
            "chart_clicks": json.dumps(chart_clicks),
            "chart_conversions": json.dumps(chart_conversions),
        },
    )


@router.get("/campaigns", response_class=HTMLResponse)
async def dashboard_campaigns(request: Request):
    campaigns = _safe_ads_data(lambda: __import__("app.google_ads.report_service", fromlist=["ReportService"]).ReportService().get_campaign_performance("LAST_7_DAYS"))
    return templates.TemplateResponse(
        "dashboard/campaigns.html",
        {"request": request, "campaigns": campaigns},
    )


@router.get("/budgets", response_class=HTMLResponse)
async def dashboard_budgets(request: Request, db: Session = Depends(get_db)):
    from app.google_ads.budget_service import BudgetService
    from app.db.models import BudgetMonthlyCap

    budgets = _safe_ads_data(lambda: BudgetService().get_all_campaign_budgets())
    month_year = date.today().strftime("%Y-%m")
    caps = {
        c.campaign_resource: c
        for c in db.query(BudgetMonthlyCap).filter(BudgetMonthlyCap.month_year == month_year).all()
    }
    return templates.TemplateResponse(
        "dashboard/budgets.html",
        {"request": request, "budgets": budgets, "caps": caps, "month_year": month_year},
    )
