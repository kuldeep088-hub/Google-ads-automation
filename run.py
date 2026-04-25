import logging
import uvicorn
from app.database import init_db
from app.jobs.scheduler import create_scheduler, register_jobs
from app.config import settings

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

init_db()
logger.info("Database tables ready.")

scheduler = create_scheduler()
register_jobs(scheduler)
scheduler.start()
logger.info("APScheduler started with %d jobs.", len(scheduler.get_jobs()))

if __name__ == "__main__":
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level=settings.LOG_LEVEL.lower(),
    )
