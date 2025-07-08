from datetime import datetime, timedelta
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.background import BackgroundTask
from sqlalchemy import select, update
from sqlalchemy.exc import PendingRollbackError
import asyncio
import logging

from src.services.templates import templates
from src.models import Episodes, Series, ListEntries, AuditLogEntry
from src.db import SessionLocal
from src.routes.template_data import popular_tv_shows
from src.cal_logic.gather import fetch_data

logger = logging.getLogger(__name__)

# add episode data to Episodes table in db
def add_episodes(series_id, edata):
    for episode in edata:
        ep_id = episode.get("id")
        ep_name = episode.get("name")
        ep_season = episode.get("season")
        ep_number = episode.get("number")
        ep_airdate_str = episode.get("airdate")
        ep_airdate = datetime.strptime(ep_airdate_str, "%Y-%m-%d")
        # filter episodes so only episodes between one year ago and one year into the future get into the calendar
        one_year_ago = datetime.now() - timedelta(days=365)
        one_year_future = datetime.now() + timedelta(days=365)
        if ep_airdate >= one_year_ago and ep_airdate <= one_year_future:
            
            episodes = Episodes(ep_series_id=int(series_id), ep_id=ep_id, ep_name=ep_name, ep_season=ep_season, ep_number=ep_number, ep_airdate=ep_airdate)
            with SessionLocal() as session:
                session.add(episodes)
                session.commit()

# add TV show to ListEntries table and Series table
async def add_to_series(request: Request):
    form = await request.form()
    series_id_form = form.get("series-id")  # "series-id" is taken from search_result.html input name value
    list_id_form = form.get('list-id')
    series_name = form.get("series-name")
    message = f"{series_name} has been added"
    try:  # validate input
        series_id = int(series_id_form) 
        list_id = int(list_id_form)
    except:
        message = "Error: Invalid input. Try again, but no tricks this time ;)"
        return templates.TemplateResponse("index.html", {"request": request, "message": message, "popular_tv_shows": popular_tv_shows})
    with SessionLocal() as session:
        try:
            series_exist = session.get(Series, series_id)
            
            le_exist = session.scalars(select(ListEntries).where(
                    ListEntries.list_id == int(list_id),
                    ListEntries.series_id == int(series_id)
                )
            ).first()

            le_exist_archive = session.scalars(select(ListEntries).where(
                    ListEntries.list_id == int(list_id),
                    ListEntries.series_id == int(series_id),
                    ListEntries.archive == 1
                )
            ).first()

            # ListEntries logic
            if le_exist is not None:
                if le_exist_archive is not None:
                    
                    session.execute(update(ListEntries).where(
                        ListEntries.list_id == int(list_id),
                        ListEntries.series_id == int(series_id)
                    )
                    .values(archive=0)
                    .execution_options(synchronize_session="fetch"))
                    
                    session.commit()
                    message = f"{series_exist.series_name} has been moved to main"
                else:
                    message = f"{series_name} is already in list {list_id}"
                redirect_url = f"/list/{list_id}"
                return RedirectResponse(url=redirect_url)
            elif le_exist is None:
                add_series = ListEntries(list_id=int(list_id), series_id=int(series_id))
                session.add(add_series)
                session.commit()

                audit_log_entry = AuditLogEntry(
                    msg_type_id = 1,
                    msg_type_name = "series_add",
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

                # Series logic
                if not series_exist:
                    today = datetime.now()
                    series_url = f"https://api.tvmaze.com/shows/{series_id}"
                    episode_url = f"https://api.tvmaze.com/shows/{series_id}/episodes"
                    # Create async tasks
                    task1 = asyncio.create_task(fetch_data(series_url))
                    task2 = asyncio.create_task(fetch_data(episode_url))
                    # Wait for tasks to complete
                    sdata = await task1
                    edata = await task2
                    # Assign series variables
                    series_status = sdata.get("status")
                    series_ext_thetvdb = sdata["externals"].get("thetvdb")
                    series_ext_imdb = sdata["externals"].get("imdb")
                    # Add TV show to Series
                    series = Series(series_id=int(series_id), series_name=series_name, series_status=series_status, series_ext_thetvdb=series_ext_thetvdb, series_ext_imdb=series_ext_imdb, series_last_updated=today)
                    session.add(series)
                    session.commit()
                    episode_task = BackgroundTask(add_episodes, series_id=series_id, edata=edata)
                    logger.info(f"{series_name} has been added")

                    return templates.TemplateResponse("index.html", {"request": request, "message": message, "popular_tv_shows": popular_tv_shows}, background=episode_task)
        except PendingRollbackError:
            session.rollback()
            logger.error("PendingRollbackError occurred. Transaction was rolled back.")
            message = "An error occurred. Please try again."
            return templates.TemplateResponse("index.html", {"request": request, "message": message, "popular_tv_shows": popular_tv_shows})
        except Exception as err:
            session.rollback()
            logger.error(f"An error occurred: {err}")
            message = "An error occurred while processing your request."
            return templates.TemplateResponse("index.html", {"request": request, "message": message, "popular_tv_shows": popular_tv_shows})
        redirect_url = f"/list/{list_id}"
        return RedirectResponse(url=redirect_url)

# move TV show from Main to Archive
async def add_to_archive(request: Request):
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
        show_exists = session.scalars(select(ListEntries).where(
                ListEntries.list_id == int(list_id),
                ListEntries.series_id == int(series_id)
            )
        ).first()
        if show_exists is not None:
            session.execute(update(ListEntries).where(
                        ListEntries.list_id == int(list_id),
                        ListEntries.series_id == int(series_id)
                    )
                    .values(archive=1)
                    .execution_options(synchronize_session="fetch"))
            session.commit()

    audit_log_entry = AuditLogEntry(
        msg_type_id = 2,
        msg_type_name = "series_archive",
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