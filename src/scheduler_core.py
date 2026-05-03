from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.events import EVENT_JOB_ERROR
import logging

from src.db import engine

logger = logging.getLogger(__name__)


jobstores = {
    'default': SQLAlchemyJobStore(engine=engine), 
    'single_show_updates': SQLAlchemyJobStore(engine=engine),
    'ntfy': SQLAlchemyJobStore(engine=engine)
}

scheduler = AsyncIOScheduler(jobstores=jobstores)
if not scheduler.running:
    scheduler.start()

logger.warning(f"DEBUG SCHEDULER: scheduler core {id(scheduler)}")
#print("DEBUG: Adding listener to scheduler instance...")
#scheduler.add_listener(error_listener, EVENT_JOB_ERROR)

def get_scheduler():
    logger.warning(f"DEBUG SCHEDULER: scheduler core get_scheduler() {id(scheduler)}")
    return scheduler
