from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
#from apscheduler.events import EVENT_JOB_ERROR
import logging

from src.db import engine

logger = logging.getLogger(__name__)


jobstores = {
    'default': SQLAlchemyJobStore(engine=engine), 
    'single_show_updates': SQLAlchemyJobStore(engine=engine),
    'ntfy': SQLAlchemyJobStore(engine=engine)
}

scheduler = AsyncIOScheduler(jobstores=jobstores)

def start_scheduler():
    if not scheduler.running:
        scheduler.start()

#scheduler.add_listener(error_listener, EVENT_JOB_ERROR)

def get_scheduler():
    return scheduler
