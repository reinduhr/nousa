from apscheduler.triggers.date import DateTrigger
import logging
from datetime import datetime, timedelta

from src.scheduler_core import get_scheduler

logger = logging.getLogger(__name__)

scheduler = get_scheduler()

def schedule_next_in_chain(series_list, index):
    """Schedules the update for the series at the given index."""
    if index >= len(series_list):
        logger.info("Chain update complete.")
        return

    try:
        series_id = series_list[index]
        
        scheduler.add_job(
            func='src.tasks.series_update_task:series_update_task',
            args=[series_id, series_list, index], # Pass the list and current index
            trigger=DateTrigger(run_date=datetime.now() + timedelta(minutes=10)),
            id=f'series_update_{series_id}',
            name=f'series_update_{series_id}',
            misfire_grace_time=518400, # 6 days
            coalesce=True, # if multiple jobs did not run, discard all others and run only one job.
            jobstore='single_show_updates',
            replace_existing=True
        )

    except Exception:
        logger.exception(f"Caught an exception during the scheduling of a series update")