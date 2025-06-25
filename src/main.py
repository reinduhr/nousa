from starlette.applications import Starlette
from starlette.responses import RedirectResponse, StreamingResponse, JSONResponse
from starlette.requests import Request
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.background import BackgroundTask

import requests
import aiohttp
import asyncio

from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import PendingRollbackError

from .ui_data import popular_tv_shows
from .mail import Mailer, send_weekly_notification_email
from .models import Series, Episodes, Lists, ListEntries, AuditLogEntry, JellyfinRecommendation
from .db import engine, SessionLocal
from .jellyfin import update_recommendations

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.base import ConflictingIdError

import subprocess
import io
import re
from datetime import datetime, timedelta
from pathlib import Path
import time
import logging
from logging.handlers import TimedRotatingFileHandler

# instantiating the web templates
templates = Jinja2Templates(directory="templates")

# delete unused files
old_log_file = Path('/code/data/nousa.log')
old_calendar_file = Path('/code/data/nousa.ics')
if old_log_file.is_file():
    old_log_file.unlink()
if old_calendar_file.is_file():
    old_calendar_file.unlink()

# logging
logging.basicConfig(encoding='utf-8', level=logging.DEBUG)
logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)
logging.getLogger('apscheduler').setLevel(logging.DEBUG)
def open_log():
    log_path = Path('/code/data/log')
    log_path.mkdir(parents=True, mode=0o770, exist_ok=True)
    file_handler = TimedRotatingFileHandler('/code/data/log/nousa.log', when='midnight', interval=7, backupCount=12, encoding='utf-8') # Create a FileHandler to log messages to a file
    formatter = logging.Formatter('%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s', datefmt='%d-%b-%Y %H:%M:%S') # Create a formatter to specify the log message format
    file_handler.setFormatter(formatter) # Set the Formatter for the FileHandler
    logging.root.addHandler(file_handler) # Add the FileHandler to the root logger. root logger has most permissions
try:
    open_log()
except Exception as err:
    logging.error(f"can't open log: {err}")

# route for home page
async def homepage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "popular_tv_shows": popular_tv_shows})

# route for search and search results
async def search(request: Request):
    form = await request.form()
    series_name = form.get('series-name')
    try:
        response = requests.get(f"https://api.tvmaze.com/search/shows?q={series_name}", timeout=10)
    except Exception as err:
        return templates.TemplateResponse("index.html", {"request": request, "popular_tv_shows": popular_tv_shows, "message": err})
    data = response.json()
    with SessionLocal() as session:
        lists = session.scalars(select(Lists)).all()
        return templates.TemplateResponse('search_result.html', {'request': request, 'data': data, 'lists': lists})
    
# route for jellyfin recommendations
async def jelly_rec(request: Request):
    with SessionLocal() as session:
        recommendations = session.scalars(select(JellyfinRecommendation)).all()
        lists = session.scalars(select(Lists)).all()
        return templates.TemplateResponse('jelly_rec.html', {'request': request, 'lists': lists, 'recommendations': recommendations, 'selected_recs': True})

# asynchronous api calls used in add_to_database()
async def fetch_data(url):
    async with aiohttp.ClientSession() as aiosession:
	    async with aiosession.get(url) as aioresponse:
                return await aioresponse.json()

# scheduler runs a weekly cronjob; 'series_update'
# the function 'series_update' runs 'try_request_series'
# the function 'try_request_series' runs 'request_series', and retries if it fails
# After a successful run all TV show data has been refreshed
def request_series(series_id):
    try:
        response_series = requests.get(f"https://api.tvmaze.com/shows/{series_id}", timeout=10)
        response_series.raise_for_status()
        return response_series.json()
    except:
        return None

def try_request_series(series_id, max_retries=30, delay=60): # try a request every minute for half an hour, if all fail then schedule new job in 24h
    retries = 0
    while retries < max_retries:
        result = request_series(series_id)
        if result is not None:
            return result
        retries += 1
        logging.error(f'series_update series retry {retries}')
        time.sleep(delay)
    try: # check if job already exists in order to avoid conflict when adding job to db
        existing_job = scheduler.get_job(job_id=f'series_update_retry_request_series_{series_id}')
        if existing_job:
            logging.info("series_update_retry_request_series job already exists. not adding new job.")
        else:
            scheduler.add_job(
                func=series_update,
                args=[series_id],
                trigger=DateTrigger(run_date=datetime.now() + timedelta(hours=24)),
                id=f'series_update_retry_request_series_{series_id}',
                coalesce=True
            )
    except ConflictingIdError as err:
        logging.error(err)
    return None

def request_episodes(series_id):
    try:
        response_episodes = requests.get(f"https://api.tvmaze.com/shows/{series_id}/episodes", timeout=10)
        response_episodes.raise_for_status()
        return response_episodes.json()
    except:
        return None

def try_request_episodes(series_id, max_retries=30, delay=60): # try a request every minute for half an hour, if all fail then schedule new job in 24h
    retries = 0
    while retries < max_retries:
        result = request_episodes(series_id)
        if result is not None:
            return result
        retries += 1
        logging.error(f'series_update episodes retry {retries}')
        time.sleep(delay)
    try: # check if job already exists in order to avoid conflict when adding job to db
        existing_job = scheduler.get_job(job_id=f'series_update_retry_request_episodes_{series_id}')
        if existing_job:
            logging.info("series_update_retry_request_series job already exists. not adding new job.")
        else:
            scheduler.add_job(
                func=series_update,
                args=[series_id],
                trigger=DateTrigger(run_date=datetime.now() + timedelta(hours=24)),
                id=f'series_update_retry_request_episodes_{series_id}',
                coalesce=True
            )
    except ConflictingIdError as err:
        logging.error(err)
    return None

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
                    logging.info(f"{series_name} has been added")

                    return templates.TemplateResponse("index.html", {"request": request, "message": message, "popular_tv_shows": popular_tv_shows}, background=episode_task)
        except PendingRollbackError:
            session.rollback()
            logging.error("PendingRollbackError occurred. Transaction was rolled back.")
            message = "An error occurred. Please try again."
            return templates.TemplateResponse("index.html", {"request": request, "message": message, "popular_tv_shows": popular_tv_shows})
        except Exception as err:
            session.rollback()
            logging.error(f"An error occurred: {err}")
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
            logging.info(f"job run time: {job_run_time}")

            try:
                existing_job = scheduler.get_job(job_id=f'series_update_{series_id}')
                if existing_job:
                    logging.info(f"series_update_{series_id} job already exists. not adding new job.")
                else:
                    scheduler.add_job(
                        func=series_update,
                        args=[series_id],
                        trigger=DateTrigger(run_date=job_run_time),
                        id=f'series_update_{series_id}',
                        name=f'series_update_{series_id}',
                        coalesce=True, # if multiple jobs did not run, discard all others and run only one job.
                        jobstore='single_show_updates'
                    )
            except ConflictingIdError as err:
                logging.error(err)

def reschedule_series_update_missed_jobs():
    now = datetime.now()
    missed_jobs = []

    job_exists = scheduler.get_job(job_id='series_update', jobstore='default')
    if job_exists and job_exists.next_run_time.replace(tzinfo=None) < now:
        scheduler.remove_all_jobs(jobstore='single_show_updates')
        return

    for job in scheduler.get_jobs():
        next_run = job.next_run_time.replace(tzinfo=None)
        if next_run and next_run < now:
            missed_jobs.append(job)

    for index, job in enumerate(missed_jobs):
        rescheduled_run_time = now + timedelta(minutes=(5 * (index+1)))
        logging.info(f"debug reschedule missed job: {job}")
        scheduler.reschedule_job(
            job_id=job.id,
            trigger=DateTrigger(run_date=rescheduled_run_time)
        )

def series_update(series_id):
    sdata = try_request_series(series_id)
    edata = try_request_episodes(series_id)
    if not sdata:
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
            if not edata:
                # Delete old episode data
                session.execute(delete(Episodes).where(Episodes.ep_series_id == series_id))
                session.commit()
                # Add new episode data
                add_episodes(series_id, edata)
            session.commit()
            logging.info("series_update success. series_id: %s", series_id)

# a redirect to handle download link from before Lists were added
def download_redirect(request: Request):
    return RedirectResponse(url=f"/subscribe/1")

# download calendar
def download_calendar(request: Request):
    list_id = request.path_params['list_id']
    calendar_file_memory = io.BytesIO()
    calendar_file_memory.write(b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:nousa\nCALSCALE:GREGORIAN\n")

    with SessionLocal() as session:
        shows = session.execute(select(Series)
            .join(ListEntries, Series.series_id == ListEntries.series_id)
            .where(ListEntries.list_id == list_id)
        ).scalars().all()

        episodes = session.execute(select(Episodes)
            .join(ListEntries, Episodes.ep_series_id == ListEntries.series_id)
            .where(
                ListEntries.list_id == list_id,
                ListEntries.archive == 0
            )
        ).scalars().all()

        for show in shows:
            for episode in episodes:
                if episode.ep_series_id == show.series_id:
                    now = datetime.now()
                    ep_start = episode.ep_airdate + timedelta(days=1) # add one day for proper calendar event start date
                    ep_end = episode.ep_airdate + timedelta(days=2) # add two days for event end
                    start_convert = datetime.strftime(ep_start,'%Y%m%d') # convert datetime object to string
                    end_convert = datetime.strftime(ep_end,'%Y%m%d') # convert datetime object to string
                    
                    calendar_event = (
                        "BEGIN:VEVENT\n"
                        f"DTSTAMP:{now:%Y%m%d}T{now:%H%M%S}Z\n"
                        f"DTSTART;VALUE=DATE:{start_convert}\n"
                        f"DTEND;VALUE=DATE:{end_convert}\n"
                        f"DESCRIPTION:Episode name: {episode.ep_name}\\nLast updated: {show.series_last_updated:%d-%b-%Y %H:%M}\\nIMDb ID: {show.series_ext_imdb}\n"
                        f"SUMMARY:{show.series_name} S{int(episode.ep_season):02d}E{int(episode.ep_number):02d}\n"
                        f"UID:{episode.ep_id}\n"
                        "BEGIN:VALARM\n"
                        f"UID:{episode.ep_id}A\n"
                        "ACTION:DISPLAY\n"
                        f"TRIGGER;VALUE=DATE-TIME:{start_convert}T170000Z\n"
                        f"DESCRIPTION:{show.series_name} is on tv today!\n"
                        "END:VALARM\n"
                        "END:VEVENT\n"
                    )
                    
                    calendar_file_memory.write(calendar_event.encode('utf-8'))
        calendar_file_memory.write(b"END:VCALENDAR")
        calendar_file_memory.seek(0)
        logging.info(f"Calendar from {list_id} was downloaded from IP: {request.client.host}")
        headers = {'Content-Disposition': 'attachment; filename="nousa.ics"'}
        return StreamingResponse(calendar_file_memory, media_type="text/calendar", headers=headers)

#  route for /lists
async def lists_page(request: Request):
    with SessionLocal() as session:
        lists = session.execute(select(Lists)).scalars().all()
        return templates.TemplateResponse('lists.html', {'request': request, 'lists': lists, 'selected_lists': True})

# route e.g.: /list/1
async def list_page(request: Request):
    list_id_path = request.path_params['list_id']
    try:
        list_id = int(list_id_path)
    except:
        return RedirectResponse(url="/")

    with SessionLocal() as session:
        listentries_list = session.execute(select(ListEntries).where(ListEntries.list_id == list_id)).scalars().all()
        lists = session.execute(select(Lists)).scalars().all()
        list_object = session.execute(select(Lists).where(Lists.list_id == list_id)).scalars().first()

        series_array = []
        archive_array = []
        for list_item in listentries_list:
            if list_item.archive == 0:
                series_array.append(list_item.series_id)
            elif list_item.archive == 1:
                archive_array.append(list_item.series_id)

        series_list = session.execute(select(Series).where(Series.series_id.in_(series_array)).order_by(Series.series_status.desc())).scalars().all()
        archive_list = session.execute(select(Series).where(Series.series_id.in_(archive_array)).order_by(Series.series_status.desc())).scalars().all()
        archive_count = len(archive_list)
        series_count = len(series_list)

        return templates.TemplateResponse('list.html', {'request': request, 
                                                        'listentries_list': listentries_list, 
                                                        'series_list': series_list, 
                                                        'archive_list': archive_list, 
                                                        'list_id': list_id, 
                                                        'list_object': list_object, 
                                                        'lists': lists,
                                                        'archive_count': archive_count,
                                                        'series_count': series_count
                                                    })

async def create_list(request: Request):
    with SessionLocal() as session:
        lists = session.execute(select(Lists)).scalars().all()
        form_data = await request.form()
        user_input = form_data.get('create-list')
        name_check = session.execute(select(Lists).where(Lists.list_name == user_input)).scalars().first()
        # validate to only accept letters and numbers
        pattern = r'^[a-zA-Z0-9]+$'
        if not re.match(pattern, user_input):
            message = "Only letters and numbers are accepted"
            return templates.TemplateResponse('lists.html', {'request': request, 'message': message, 'lists': lists})
        else:
            if not name_check:
                new_list = Lists(list_name=user_input)
                session.add(new_list)
                session.commit()
                lists = session.execute(select(Lists)).scalars().all()
                
                message = f"{user_input} has been created"
                list_id = new_list.list_id

                audit_log_entry = AuditLogEntry(
                    msg_type_id = 4,
                    msg_type_name = "list_create",
                    ip = request.client.host,
                    list_id = list_id,
                    list_name = user_input,
                    prev_list_name = None,
                    series_id = None,
                    series_name = None,
                    created_at = datetime.now()
                )
                session.add(audit_log_entry)
                session.commit()
                
                return templates.TemplateResponse('lists.html', {'request': request, 'message': message, 'lists': lists})
            else:
                message = "A list with that name exists already"
                return templates.TemplateResponse('lists.html', {'request': request, 'message': message, 'lists': lists})

async def rename_list(request: Request):
    form_data = await request.form()
    list_id_form = form_data.get('list-id')
    user_input = form_data.get("rename-list")
    with SessionLocal() as session:
        prev = session.execute(select(Lists).where(Lists.list_id == list_id_form)).scalar_one()
        prev_list_name = prev.list_name
        try: # validate input
            list_id = int(list_id_form)
        except:
            message = "Error: Invalid input. Try again, but no tricks this time ;)"
            return templates.TemplateResponse('index.html', {'request': request, 'message': message})
        # validate to only accept letters and numbers
        pattern = r'^[a-zA-Z0-9]+$'
        if not re.match(pattern, user_input):
            message = "Only letters and numbers are accepted"
            return templates.TemplateResponse('index.html', {'request': request, 'message': message})
        name_check = session.execute(select(func.count()).where(Lists.list_name == user_input)).scalar_one()

        if name_check > 0:
            message = "A list with that name exists already"
            return templates.TemplateResponse('index.html', {'request': request, 'message': message})
        else:
            session.execute(update(Lists)
                .where(Lists.list_id == int(list_id))
                .values(list_name=user_input)
                .execution_options(synchronize_session='fetch')
            )
            session.commit()

            audit_log_entry = AuditLogEntry(
                msg_type_id = 5,
                msg_type_name = "list_rename",
                ip = request.client.host,
                list_id = list_id,
                list_name = user_input,
                prev_list_name = prev_list_name,
                series_id = None,
                series_name = None,
                created_at = datetime.now()
            )
            session.add(audit_log_entry)
            session.commit()
            
        return RedirectResponse(url=f"/list/{list_id}")

# Alembic database migrations
async def db_migrations():
    result = subprocess.run(["alembic", "upgrade", "head"], capture_output=True, text=True)
    if result.returncode != 0:
        logging.error(f"Alembic database migrations failed: {result.stderr}")

# scheduler
jobstores = {
    'default': SQLAlchemyJobStore(engine=engine), 
    'single_show_updates': SQLAlchemyJobStore(engine=engine)
}
scheduler = AsyncIOScheduler(jobstores=jobstores)
scheduler.start(paused=True)
reschedule_series_update_missed_jobs()
scheduler.resume()
# check if series_update job already exists in order to avoid conflict when adding job to db
try:
    existing_job = scheduler.get_job(job_id='series_update')
    if existing_job:
        logging.info("series_update job already exists. not adding new job.")
    else:
        scheduler.add_job(
            func=schedule_series_update,
            trigger=CronTrigger(day_of_week='sun', hour=1, jitter=600), # job runs every Sunday around 1AM
            id='series_update',
            coalesce=True, # if multiple jobs did not run, discard all others and run only one job
            jobstore='default'
        )
except ConflictingIdError as err:
    logging.error(err)

try:
    #scheduler.remove_job(job_id="weekly_notification_email")
    existing_job = scheduler.get_job(job_id="weekly_notification_email")
    if not existing_job:
        scheduler.add_job(
            func=send_weekly_notification_email,
            #trigger=IntervalTrigger(minutes=400),
            trigger=CronTrigger(day_of_week='wed', hour=9, jitter=600),
            id="weekly_notification_email",
            name="weekly_notification_email",
            coalesce=True,
            jobstore='default'
        )
except ConflictingIdError as err:
    logging.error(err)

try:
    job_exists = scheduler.get_job(job_id="jellyfin_recommendation_refresh", jobstore="default")
    if job_exists != None:
        logging.info("jellyfin recommendation refresh job detected and removed")
        scheduler.remove_job(job_id="jellyfin_recommendation_refresh")
    scheduler.add_job(
        func=update_recommendations,
        trigger=CronTrigger(day=1, hour=23, jitter=600),
        #trigger=DateTrigger(run_date=datetime.now()+timedelta(seconds=10)),
        id="jellyfin_recommendation_refresh",
        name="jellyfin_recommendation_refresh",
        coalesce=True,
        jobstore="default"
    )
except Exception as err:
    logging.error("Failed to update Jellyfin recommendations:", err)

routes = [
    Route("/", endpoint=homepage, methods=["GET"]),
    Mount("/nousa", app=StaticFiles(directory="static"), name="static"),
    Route("/search", endpoint=search, methods=["GET", "POST"]),
    Route("/add_show", endpoint=add_to_series, methods=["GET", "POST"]),
    Route("/archive_show", endpoint=add_to_archive, methods=["GET", "POST"]),
    Route("/delete_show", endpoint=del_series, methods=["GET", "POST"]),
    Route("/subscribe", endpoint=download_redirect, methods=["GET"]),
    Route("/create_list", endpoint=create_list, methods=["GET", "POST"]),
    Route("/rename_list", endpoint=rename_list, methods=["GET", "POST"]),
    Route("/lists", endpoint=lists_page, methods=["GET", "POST"]),
    Route("/list/{list_id}", endpoint=list_page, methods=["GET", "POST"]),
    Route("/subscribe/{list_id}", endpoint=download_calendar, methods=["GET"]),
    Route("/recommendations", endpoint=jelly_rec, methods=["GET", "POST"])
]

#app = Starlette(debug=True, routes=routes)
app = Starlette(debug=False, routes=routes, on_startup=[db_migrations])