import logging
import asyncio
from datetime import datetime, timedelta
from apscheduler.triggers.date import DateTrigger

from src.cal_logic.update import series_update
from src.scheduler_core import get_scheduler
from src.helpers.scheduler.update import schedule_next_in_chain
from src.tasks.ntfy_task import send_ntfy_task

logger = logging.getLogger(__name__)


def series_update_task(
        series_id: int,
        series_list: list,
        index: int, 
        retry_count: int = 0
    ):
    
    if retry_count > 0:
        logger.debug(f"Running series update task (retry={retry_count})")
    
    try:
        success = series_update(series_id)
        
        if success:
            schedule_next_in_chain(series_list, index + 1)

        else:
            handle_retry(series_id, series_list, index, retry_count)

    except Exception:
        logger.exception("Caught an exception while updating series from series update task")
        handle_retry(series_id, series_list, index, retry_count)


def handle_retry(series_id, series_list, index, retry_count):
    if retry_count > 10:
        logger.error(f"Max retries reached for updating series data.")
        return asyncio.create_task(send_ntfy_task(message="Error: max retries reached for updating series data"))

    scheduler = get_scheduler()
    scheduler.add_job(
        func=series_update_task, # Call the wrapper, not the raw logic
        args=[series_id, series_list, index], 
        kwargs={"retry_count": retry_count + 1},
        trigger=DateTrigger(run_date=datetime.now() + timedelta(hours=4)),
        id=f"series_update_{series_id}_retry",
        replace_existing=True
    )