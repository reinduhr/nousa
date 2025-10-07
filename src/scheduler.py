from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.base import ConflictingIdError

from sqlalchemy import select

import os
import logging
from datetime import datetime, timedelta

from src.models import Series
from src.db import engine, SessionLocal
from src.services.mail import send_weekly_notification_email
from src.cal_logic.update import series_update
from services.sonarr import sync_nousa_sonarr

logger = logging.getLogger(__name__)

# scheduler
jobstores = {
    'default': SQLAlchemyJobStore(engine=engine), 
    'single_show_updates': SQLAlchemyJobStore(engine=engine)
}
scheduler = AsyncIOScheduler(jobstores=jobstores)

def start_scheduler():

    scheduler.start(paused=True)
    scheduler.remove_all_jobs() # remove all because existing jobs can have incorrect path which breaks server startup
    scheduler.resume()

    # check if series_update job already exists in order to avoid conflict when adding job to db
    try:
        existing_job = scheduler.get_job(job_id='series_update')
        if not existing_job:
            scheduler.add_job(
                func=schedule_series_update,
                trigger=CronTrigger(day_of_week='sun', hour=1, jitter=600), # job runs every Sunday around 1AM
                id='series_update',
                misfire_grace_time=600,
                coalesce=True, # if multiple jobs did not run, discard all others and run only one job
                jobstore='default'
            )
    except ConflictingIdError as err:
        logger.error(err)

    try:
        existing_job = scheduler.get_job(job_id="weekly_notification_email")
        if not existing_job:
            scheduler.add_job(
                func=send_weekly_notification_email,
                trigger=CronTrigger(day_of_week='wed', hour=9, jitter=600),
                id="weekly_notification_email",
                name="weekly_notification_email",
                misfire_grace_time=600,
                coalesce=True,
                jobstore='default'
            )
    except ConflictingIdError as err:
        logger.error(err)

    try:
        scheduler.add_job(
            func=sync_nousa_sonarr,
            trigger=CronTrigger(hour=0),
            id="sync_nousa_to_sonarr",
            name="sync_nousa_to_sonarr",
            coalesce=True,
            jobstore="default"
        )
    except Exception as err:
        logger.error(err)

# series_update refreshes series and episodes data. scheduler automates it.
def schedule_series_update():
    if scheduler.get_job(job_id='update_series'):
        scheduler.remove_job(job_id='update_series')
    with SessionLocal() as session:
        series_list = session.execute(select(Series.series_id)).scalars().all()
        # Series
        for index, series_id in enumerate(series_list):
            now = datetime.now()
            job_run_time = now + timedelta(minutes=(5 * index))
            logger.info(f"job run time: {job_run_time}")

            try:
                existing_job = scheduler.get_job(job_id=f'series_update_{series_id}')
                if existing_job:
                    logger.info(f"series_update_{series_id} job already exists. not adding new job.")
                else:
                    scheduler.add_job(
                        func=series_update,
                        args=[series_id],
                        trigger=DateTrigger(run_date=job_run_time),
                        id=f'series_update_{series_id}',
                        name=f'series_update_{series_id}',
                        misfire_grace_time=518400, # 6 days
                        coalesce=True, # if multiple jobs did not run, discard all others and run only one job.
                        jobstore='single_show_updates'
                    )
            except ConflictingIdError as err:
                logger.error(err)