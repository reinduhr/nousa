from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.base import ConflictingIdError

from sqlalchemy import select

import logging
from datetime import datetime, timedelta

from src.models import Series
from src.db import SessionLocal
from src.services.mail import send_weekly_notification_email
from src.tasks.series_update_task import series_update_task
from src.services.sonarr import sync_nousa_sonarr
from src.scheduler_core import get_scheduler

logger = logging.getLogger(__name__)

scheduler = get_scheduler()


def schedule_default_jobs():
    
    try:
        scheduler.add_job(
            func=schedule_series_update,
            trigger=CronTrigger(day_of_week='sun', hour=1, jitter=600), # job runs every Sunday around 1AM
            #trigger=DateTrigger(run_date=datetime.now() + timedelta(seconds=30)),
            id='series_update',
            misfire_grace_time=600,
            coalesce=True, # if multiple jobs did not run, discard all others and run only one job
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
            misfire_grace_time=600,
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
        
        for index, series_id in enumerate(series_list):
            now = datetime.now()
            
            job_run_time = now + timedelta(minutes=(5 * index))
            logger.info(f"job run time: {job_run_time}")

            schedule_series_update_by_id(series_id, job_run_time)


def schedule_series_update_by_id(series_id, job_run_time):
    
    try:

        scheduler.add_job(
            func=series_update_task,
            args=[series_id],
            trigger=DateTrigger(run_date=job_run_time),
            id=f'series_update_{series_id}',
            name=f'series_update_{series_id}',
            misfire_grace_time=518400, # 6 days
            coalesce=True, # if multiple jobs did not run, discard all others and run only one job.
            jobstore='single_show_updates',
            replace_existing=True
        )
            
    except Exception:
        logger.exception(f"Caught an exception during the scheduling of a series update")