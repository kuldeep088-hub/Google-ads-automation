import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routers import dashboard, rules, campaigns, budgets, reports, jobs, advanced

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

app = FastAPI(title="Google Ads Automation", version="1.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(dashboard.router)
app.include_router(rules.router, prefix="/rules")
app.include_router(campaigns.router, prefix="/api/campaigns")
app.include_router(budgets.router, prefix="/budgets")
app.include_router(reports.router, prefix="/reports")
app.include_router(jobs.router, prefix="/jobs")
app.include_router(advanced.router, prefix="/advanced")
