from datetime import datetime, timedelta
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.background import BackgroundTask
from sqlalchemy import select, update
from sqlalchemy.exc import PendingRollbackError
import asyncio
import logging
from collections import defaultdict

from src.services.templates import templates
from src.models import Episodes, Series, ListEntries, AuditLogEntry, Lists
from src.db import SessionLocal
from src.routes.template_data import popular_tv_shows
from src.cal_logic.gather import fetch_data

from src.tasks.ntfy_task import send_ntfy_task

logger = logging.getLogger(__name__)

async def get_record(model, **kwargs):
    """
    Returns the record if it exists, otherwise returns None, and upon failure returns False.
    """
    with SessionLocal() as session:
        try:
            # .filter_by handles multiple keyword arguments
            result = session.query(model).filter_by(**kwargs).first()
            return result if result else None
        except Exception:
            return False


async def toggle_list_entry_archive(series_id, list_id) -> bool:
    try:

        with SessionLocal() as session:
            # This flips 0 to 1 and 1 to 0 in a single round trip
            session.execute(
                update(ListEntries)
                .where(
                    ListEntries.list_id == int(list_id),
                    ListEntries.series_id == int(series_id)
                )
                .values(archive=1 - ListEntries.archive)
                .execution_options(synchronize_session="fetch")
            )
            session.commit()
            return True
    except Exception as e:
        logger.error(f"Caught an exception: {e}")
        return False

    
async def move_to_archive():
    pass

async def add_list_entry(series_id: int, list_id: int):
   
    with SessionLocal() as session:
        
        list_entry = ListEntries(list_id=int(list_id), series_id=int(series_id), archive=0)
        session.add(list_entry)
        session.commit()



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

async def fetch_series_data(series_id):
    
    series_url = f"https://api.tvmaze.com/shows/{series_id}"
    episode_url = f"https://api.tvmaze.com/shows/{series_id}/episodes"
    
    # Create async tasks
    task1 = asyncio.create_task(fetch_data(series_url))
    task2 = asyncio.create_task(fetch_data(episode_url))
    
    # Wait for tasks to complete
    sdata = await task1
    edata = await task2

    return sdata, edata

async def add_series(sdata, edata, series_id):
    today = datetime.now()

    
    # Assign series variables
    series_status = sdata.get("status")
    series_ext_thetvdb = sdata["externals"].get("thetvdb")
    series_ext_imdb = sdata["externals"].get("imdb")
    
    # Add TV show to Series
    series = Series(series_id=int(series_id), series_name=sdata['name'], series_status=series_status, series_ext_thetvdb=series_ext_thetvdb, series_ext_imdb=series_ext_imdb, series_last_updated=today)
    
    try:
        with SessionLocal() as session:
            session.add(series)
            session.commit()
        
        episode_task = BackgroundTask(add_episodes, series_id=series_id, edata=edata)
    
    except PendingRollbackError:
            session.rollback()
            logger.error("PendingRollbackError occurred. Transaction was rolled back.")
            message = "An error occurred. Please try again."
            return
        
    except Exception as err:
            session.rollback()
            logger.error(f"An error occurred: {err}")
            message = "An error occurred while processing your request."
            return
    
    logger.info(f"{sdata['name']} has been added")
    

    return episode_task


# add TV show to ListEntries table and Series table
async def add_to_series(request: Request):
    
    form = await request.form()
    
    series_id_form = form.get("series-id")
    list_id_form = form.get('list-id')
    series_name = form.get("series-name")
    
    message = f"{series_name} has been added"
    
    try:  # validate input
        series_id = int(series_id_form) 
        list_id = int(list_id_form)
   
    except:
        message = "Error: Invalid input. Try again, but no tricks this time ;)"
        return templates.TemplateResponse(request, "index.html", {"message": message, "popular_tv_shows": popular_tv_shows})
    

    series = await get_record(Series, series_id=series_id)
    list_entry = await get_record(ListEntries, series_id=series_id, list_id=list_id)
    calendar_list = await get_record(Lists, list_id=list_id)

    sdata, edata = await fetch_series_data(series_id)

    if not series:
        episode_task = await add_series(sdata, edata, series_id)
    
    if not list_entry:
        add_list_entry(series_id, list_id)
        audit_log_entry = AuditLogEntry(
            msg_type_id = 1,
            msg_type_name = "series_add",
            ip = request.client.host,
            list_id = list_id,
            list_name = calendar_list.list_name,
            prev_list_name = None,
            series_id = series_id,
            series_name = series_name,
            created_at = datetime.now()
        )
        with SessionLocal() as session:
            session.add(audit_log_entry)
            session.commit()

    await send_ntfy_task(message=f"{sdata['name']} has been added to List {list_id}: {calendar_list.list_name}")
    return templates.TemplateResponse(request, "index.html", {"message": message, "popular_tv_shows": popular_tv_shows}, background=episode_task or None)
        


# move TV show from Main to Archive or the other way around depending
async def toggle_archive(request: Request):
    form = await request.form()
    url = request.headers.get("referer")
    
    series_id = form.get('series-id')
    list_id = form.get('list-id')
    
    result = await toggle_list_entry_archive(series_id, list_id)
    
    return RedirectResponse(url=url)


# helper function to filter search results against series in lists
def build_available_lists(lists, list_entries):
    entries_map = defaultdict(set)
    for entry in list_entries:
        entries_map[entry.series_id].add(entry.list_id)

    def get_available_lists(show_id):
        existing = entries_map.get(show_id, set())
        return [lst for lst in lists if lst.list_id not in existing]

    return get_available_lists

# moved to archive
"""
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

list_name = session.get_one(Lists, list_id).list_name
await send_ntfy_task(message=f"{series_name} has been archived on List {list_id}: {list_name}")
"""