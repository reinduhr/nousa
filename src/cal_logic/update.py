from starlette.requests import Request
from starlette.responses import RedirectResponse
from datetime import datetime
from sqlalchemy import update, delete, select, func
import logging

from src.services.templates import templates
from src.db import SessionLocal
from src.models import Series, Episodes, AuditLogEntry, ListEntries

logger = logging.getLogger(__name__)

def series_update(series_id):
    # imports go here to prevent circular import error
    from src.cal_logic.gather import try_request_series, try_request_episodes
    from src.cal_logic.input import add_episodes
    sdata = try_request_series(series_id)
    edata = try_request_episodes(series_id)
    if sdata is not None:
        today = datetime.now()
        sdata_name = sdata['name']
        sdata_status = sdata['status']
        sdata_ext_thetvdb = sdata['externals'].get('thetvdb')
        sdata_ext_imdb = sdata['externals'].get('imdb')

        with SessionLocal() as session:
            session.execute(
                update(Series)
                .where(Series.series_id == series_id)
                .values(
                    series_name=sdata_name,
                    series_status=sdata_status,
                    series_ext_thetvdb=sdata_ext_thetvdb,
                    series_ext_imdb=sdata_ext_imdb,
                    series_last_updated=today,
                )
            )

            # Episodes
            if edata is not None:
                # Delete old episode data
                session.execute(delete(Episodes).where(Episodes.ep_series_id == series_id))
                session.commit()
                # Add new episode data
                add_episodes(series_id, edata)
            session.commit()
            logger.info("series_update success. series_id: %s", series_id)

# Delete series from list. If series is not on any other list: delete all series data
async def del_series(request: Request):
    form_data = await request.form()
    series_id_form = form_data['series-id'] # input id of serie to be deleted
    list_id_form = form_data['list-id']
    series_name = form_data['series-name']
    try:
        series_id = int(series_id_form) # validate input
        list_id = int(list_id_form)
    except:
        message = "Error: Invalid input. Try again, but no tricks this time"
        return templates.TemplateResponse("index.html", {"request": request, "message": message})
    with SessionLocal() as session:
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
    
        audit_log_entry = AuditLogEntry(
            msg_type_id = 3,
            msg_type_name = "series_delete",
            ip = request.client.host,
            list_id = list_id,
            list_name = None,
            prev_list_name = None,
            series_id = series_id,
            series_name = series_name,
            created_at = datetime.now()
        )
        session.add(audit_log_entry)
        session.commit()

        redirect_url = f"/list/{list_id}"
        return RedirectResponse(url=redirect_url)