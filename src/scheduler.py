from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from sqlalchemy import select

import logging

from src.models import Series
from src.db import SessionLocal
from src.services.mail import send_weekly_notification_email
from src.services.sonarr import sync_nousa_sonarr
from src.scheduler_core import get_scheduler
from src.helpers.scheduler.update import schedule_next_in_chain

logger = logging.getLogger(__name__)

scheduler = get_scheduler()


def schedule_default_jobs():
    
    try:
        scheduler.add_job(
            func=schedule_series_update,
            trigger=CronTrigger(day_of_week='sun', hour=1, jitter=600), # job runs every Sunday around 1AM
            #trigger=DateTrigger(run_date=datetime.now() + timedelta(seconds=30)),
            id='series_update',
            misfire_grace_time=345600, # 4 days
            coalesce=True,
            jobstore='default', 
            replace_existing=True
        )
    except Exception:
        logger.exception("Caught an exception scheduling series update")

    try:
        scheduler.add_job(
            func=send_weekly_notification_email,
            trigger=CronTrigger(day_of_week='wed', hour=9, jitter=600),
            id="weekly_notification_email",
            name="weekly_notification_email",
            misfire_grace_time=345600,
            coalesce=True,
            jobstore='default',
            replace_existing=True
        )
    except Exception:
        logger.exception("Caught an exception scheduling the weekly notification email")

    try:
        scheduler.add_job(
            func=sync_nousa_sonarr,
            trigger=CronTrigger(hour=0),
            id="sync_nousa_to_sonarr",
            name="sync_nousa_to_sonarr",
            misfire_grace_time=3600,
            coalesce=True,
            jobstore='default',
            replace_existing=True
        )
    except Exception:
        logger.exception("Caught an exception scheduling the nousa sonarr sync service")

# series_update refreshes series and episodes data. scheduler automates it.
def schedule_series_update():
    
    with SessionLocal() as session:
        
        series_list = session.execute(select(Series.series_id)).scalars().all()

        if not series_list:
            logger.info("No series found to update.")
            return
        
        schedule_next_in_chain(series_list, index=0)
