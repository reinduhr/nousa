from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqlalchemy import delete, select, func
import logging

from src.models import Series, Episodes, ListEntries
from src.services.templates import templates
from src.db import SessionLocal
from src.helpers.logging import add_audit_log_entry

from src.tasks.ntfy_task import send_ntfy_task

logger = logging.getLogger(__name__)


# Delete series from list. If series is not on any other list: delete all series data
async def del_series(request: Request):
    form_data = await request.form()
    url = request.headers.get("referer")
    
    series_id_form = form_data['series-id'] # input id of serie to be deleted
    list_id_form = form_data['list-id']
    series_name = form_data['series-name']
    list_name = form_data['list-name']
    
    try:
        series_id = int(series_id_form) # validate input
        list_id = int(list_id_form)
    except:
        message = "Error: Invalid input. Try again, but no tricks this time"
        return templates.TemplateResponse(request, "index.html", {"message": message})
    
    with SessionLocal() as session:
        try:
            le_count = session.execute(select(func.count()).where(ListEntries.series_id == series_id)).scalar_one()
            
            if le_count > 1: # if series is on more than 1 list: delete entry from ListEntries
                session.execute(delete(ListEntries).where(
                    (ListEntries.series_id == series_id) & (ListEntries.list_id == list_id)
                ))
                session.commit()
            
            if le_count <= 1: # if series is on 1 or less lists: delete everything
                session.execute(delete(Episodes).where(Episodes.ep_series_id == series_id))
                session.execute(delete(ListEntries).where(ListEntries.series_id == series_id))
                session.execute(delete(Series).where(Series.series_id == series_id))
                session.commit()

            await add_audit_log_entry(
                msg_type_id = 3,
                msg_type_name = "series_delete",
                ip = request.client.host,
                list_id = list_id,
                list_name = list_name,
                prev_list_name = None,
                series_id = series_id,
                series_name = series_name)
            
            await send_ntfy_task(message=f"{series_name} has been deleted from List {list_id}: {list_name}")

            url = f"/list/{list_id}"
            return RedirectResponse(url)
        
        except Exception:
            logger.exception("error while deleting series")