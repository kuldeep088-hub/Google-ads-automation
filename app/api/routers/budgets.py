import logging
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import BudgetMonthlyCap

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.post("/caps")
async def set_monthly_cap(
    campaign_resource: str = Form(...),
    cap_usd: float = Form(...),
    db: Session = Depends(get_db),
):
    month_year = date.today().strftime("%Y-%m")
    cap_micros = int(cap_usd * 1_000_000)
    existing = (
        db.query(BudgetMonthlyCap)
        .filter(
            BudgetMonthlyCap.campaign_resource == campaign_resource,
            BudgetMonthlyCap.month_year == month_year,
        )
        .first()
    )
    if existing:
        existing.cap_micros = cap_micros
    else:
        db.add(BudgetMonthlyCap(
            campaign_resource=campaign_resource,
            month_year=month_year,
            cap_micros=cap_micros,
        ))
    db.commit()
    return {"status": "ok", "cap_usd": cap_usd, "month_year": month_year}


@router.get("/caps")
async def list_caps(db: Session = Depends(get_db)):
    caps = db.query(BudgetMonthlyCap).order_by(BudgetMonthlyCap.month_year.desc()).limit(50).all()
    return [
        {
            "id": c.id,
            "campaign_resource": c.campaign_resource,
            "month_year": c.month_year,
            "cap_usd": c.cap_micros / 1_000_000,
            "spent_usd": c.spent_micros / 1_000_000,
            "pct_used": round(c.spent_micros / max(c.cap_micros, 1) * 100, 1),
            "is_paused_by_cap": c.is_paused_by_cap,
        }
        for c in caps
    ]


@router.post("/unpause/{campaign_resource:path}")
async def unpause_campaign(campaign_resource: str):
    from app.google_ads.budget_service import BudgetService
    success = BudgetService().enable_campaign(campaign_resource)
    return {"success": success}
