from datetime import datetime, timedelta
from apscheduler.triggers.date import DateTrigger 
import logging
import uuid
from scheduler_core import get_scheduler
from src.services.ntfy import send_ntfy

logger = logging.getLogger(__name__)


async def send_ntfy_task(
        message: str,
        topic: str = "nousa",
        title: str = "📅 nousa 📺 tv calendar",
        priority: str = "3",
        retry_count: int = 0
    ):
    
    if retry_count > 0:
        logger.info(f"Running ntfy task (retry={retry_count})")

    try:
        await send_ntfy(message, topic, title, priority)
    
    except Exception as e:
        logger.error(f"Caught an exception while trying to send ntfy: {e}")

        if retry_count >= 10:
            logger.error("Max retries reached, giving up")
            raise

        delay = 2 ** retry_count * 60

        scheduler = get_scheduler()

        scheduler.add_job(
            func=send_ntfy_task,
            trigger=DateTrigger(run_date=datetime.now() + timedelta(seconds=delay)),
            kwargs={
                "message": message,
                "topic": topic,
                "title": title,
                "priority": priority,
                "retry_count": retry_count + 1,
            },
            id=f"ntfy_retry_{uuid.uuid4()}",
            replace_existing=True,
            jobstore="ntfy"
        )
