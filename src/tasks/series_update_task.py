import logging
from datetime import datetime, timedelta
from apscheduler.triggers.date import DateTrigger

from src.cal_logic.update import series_update
from src.scheduler_core import get_scheduler

logger = logging.getLogger(__name__)


def series_update_task(
        series_id: int, 
        retry_count: int = 0
    ):
    
    if retry_count > 0:
        logger.info(f"Running series update task (retry={retry_count})")
    
    try:
        series_update(series_id)

    except Exception:
        logger.exception("Caught an exception while updating series from series update task")

        if retry_count > 20:
            logger.error("Max retries reached, giving up")
            raise

        scheduler = get_scheduler()

        scheduler.add_job(
            func=series_update,
            args=[series_id],
            trigger=DateTrigger(run_date=datetime.now() + timedelta(hours=4)),
            kwargs={
                "retry_count": retry_count + 1,
            },
            id=f"series_update_{series_id}_retry",
            replace_existing=True,
            jobstore="single_show_updates"
        )