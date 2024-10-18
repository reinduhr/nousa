from starlette.applications import Starlette
from starlette.responses import RedirectResponse, StreamingResponse
from starlette.requests import Request
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.background import BackgroundTask
import requests
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, PendingRollbackError
from .init_models import Base
from .models import engine, Series, Episodes, Lists, ListEntries
from datetime import datetime, timedelta
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.base import ConflictingIdError
from pathlib import Path
import time
import logging
from logging.handlers import TimedRotatingFileHandler
import secrets
import aiohttp
import asyncio
from .ui_data import popular_tv_shows
import subprocess
import io
import re # regular expression

inspector = inspect(engine)
existing_tables = inspector.get_table_names()
if 'series' not in existing_tables:
    Base.metadata.create_all(engine)

async def db_migrations():
    result = subprocess.run(["alembic", "upgrade", "head"], capture_output=True, text=True)
    if result.returncode != 0:
        logging.error(f"Alembic database migrations failed: {result.stderr}")

# Create SQLAlchemy session
Session = sessionmaker(bind=engine)
session = Session()
# Instantiating the web templates
templates = Jinja2Templates(directory="templates")
# Delete unused files
old_log_file = Path('/code/data/nousa.log')
old_calendar_file = Path('/code/data/nousa.ics')
if old_log_file.is_file():
    old_log_file.unlink()
if old_calendar_file.is_file():
    old_calendar_file.unlink()
# Logging
logging.basicConfig(encoding='utf-8', level=logging.INFO)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
logging.getLogger('apscheduler').setLevel(logging.INFO)
def open_log():
    log_path = Path('/code/data/log')
    log_path.mkdir(parents=True, mode=0o770, exist_ok=True)
    file_handler = TimedRotatingFileHandler('/code/data/log/nousa.log', when='midnight', interval=7, backupCount=12, encoding='utf-8') # Create a FileHandler to log messages to a file
    formatter = logging.Formatter('%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s', datefmt='%d-%b-%Y %H:%M:%S') # Create a formatter to specify the log message format
    file_handler.setFormatter(formatter) # Set the Formatter for the FileHandler
    logging.root.addHandler(file_handler) # Add the FileHandler to the root logger. root logger has most permissions
try:
    open_log()
except:
    logging.error("can't open log")
# Audit Logging
def setup_audit_logger():
    audit_logger = logging.getLogger('audit_logger')
    audit_logger.setLevel(logging.INFO)
    audit_handler = logging.FileHandler('/code/data/log/audit.log')
    audit_handler.setLevel(logging.INFO)
    audit_formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%d-%b-%Y %H:%M:%S')
    audit_handler.setFormatter(audit_formatter)
    audit_logger.addHandler(audit_handler)
    return audit_logger
audit_logger = setup_audit_logger()

async def homepage(request): # /
    return templates.TemplateResponse("index.html", {"request": request, "popular_tv_shows": popular_tv_shows})

async def search(request: Request):
    lists = session.query(Lists).all()
    form = await request.form()
    series_name = form.get('series-name')
    try:
        response = requests.get(f"https://api.tvmaze.com/search/shows?q={series_name}", timeout=10)
    except Exception as err:
        return templates.TemplateResponse("index.html", {"request": request, "popular_tv_shows": popular_tv_shows, "message": err})
    data = response.json()
    return templates.TemplateResponse('search_result.html', {'request': request, 'data': data, 'lists': lists})

async def fetch_data(url): # asynchronous api calls used in add_to_database()
    async with aiohttp.ClientSession() as aiosession:
	    async with aiosession.get(url) as aioresponse:
                return await aioresponse.json()

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
        logging.error(f'update_series series retry {retries}')
        time.sleep(delay)
    try: # check if job already exists in order to avoid conflict when adding job to db
        existing_job = scheduler.get_job(job_id='update_series_try_request_series')
        if existing_job:
            logging.info("update_series_try_request_series job already exists. not adding new job.")
        else:
            scheduler.add_job(
                update_series,
                trigger=DateTrigger(run_date=datetime.now() + timedelta(hours=24)),
                id='update_series_try_request_series',
                misfire_grace_time=86400,
                coalescing=True,
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
        logging.error(f'update_series episodes retry {retries}')
        time.sleep(delay)
    try: # check if job already exists in order to avoid conflict when adding job to db
        existing_job = scheduler.get_job(job_id='update_series_try_request_episodes')
        if existing_job:
            logging.info("update_series_try_request_series job already exists. not adding new job.")
        else:
            scheduler.add_job(
                update_series,
                trigger=DateTrigger(run_date=datetime.now() + timedelta(hours=24)),
                id='update_series_try_request_episodes',
                misfire_grace_time=86400,
                coalescing=True,
            )
    except ConflictingIdError as err:
        logging.error(err)
    return None

def add_episodes(series_id, edata):
    for element in edata:
        ep_id = element.get("id")
        ep_name = element.get("name")
        ep_season = element.get("season")
        ep_number = element.get("number")
        ep_airdate = element.get("airdate")
        date_time_obj = datetime.strptime(ep_airdate, "%Y-%m-%d")
        episodes = Episodes(ep_series_id=int(series_id), ep_id=ep_id, ep_name=ep_name, ep_season=ep_season, ep_number=ep_number, ep_airdate=date_time_obj)
        session.add(episodes)
        session.commit()

async def add_to_series(request: Request):
    form = await request.form()
    series_id_form = form.get("series-id")  # "series-id" is taken from search_result.html input name value
    list_id_form = form.get('list-id')
    series_name_form = form.get("series-name")
    message = f"{series_name_form} has been added"
    try:  # validate input
        series_id = int(series_id_form) 
        list_id = int(list_id_form)
    except:
        message = "Error: Invalid input. Try again, but no tricks this time ;)"
        return templates.TemplateResponse("index.html", {"request": request, "message": message, "popular_tv_shows": popular_tv_shows})
    try:
        series_series_id_exist = session.query(Series).get(series_id)
        series_series = session.query(Series).filter_by(series_id=int(series_id)).first()
        le_exist = session.query(ListEntries).filter_by(list_id=int(list_id), series_id=int(series_id)).count()
        le_exist_archive = session.query(ListEntries).filter_by(list_id=list_id, series_id=series_id, archive=1).count()
        # ListEntries logic
        if le_exist == 1:
            if le_exist_archive == 1:
                session.query(ListEntries).filter_by(list_id=int(list_id), series_id=int(series_id)).update({"archive": 0}, synchronize_session='fetch')
                session.commit()
                audit_logger.info(f"MOVED SHOW FROM ARCHIVE TO MAIN: {series_series.series_name} FROM IP: {request.client.host}")
                message = f"{series_series.series_name} has been moved to main"
            else:
                message = f"{series_name_form} is already in list {list_id}"
            #return templates.TemplateResponse("index.html", {"request": request, "message": message, "popular_tv_shows": popular_tv_shows})
            redirect_url = f"/list/{list_id}"
            return RedirectResponse(url=redirect_url)
        elif le_exist == 0:
            add_series = ListEntries(list_id=int(list_id), series_id=int(series_id))
            session.add(add_series)
            session.commit()
            audit_logger.info(f"ADDED SHOW: {series_name_form} FROM IP: {request.client.host}")
            # Series logic
            if not series_series_id_exist:
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
                series_name = sdata.get("name")
                series_status = sdata.get("status")
                series_ext_thetvdb = sdata["externals"].get("thetvdb")
                series_ext_imdb = sdata["externals"].get("imdb")
                # Add TV show to Series
                series = Series(series_id=int(series_id), series_name=series_name, series_status=series_status, series_ext_thetvdb=series_ext_thetvdb, series_ext_imdb=series_ext_imdb, series_last_updated=today)
                session.add(series)
                session.commit()
                episode_task = BackgroundTask(add_episodes, series_id=series_id, edata=edata)
                logging.info(f"{series_name} has been added")
                audit_logger.info(f"ADDED SHOW: {series_name} FROM IP: {request.client.host}")
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
    finally:
        session.close()
    redirect_url = f"/list/{list_id}"
    return RedirectResponse(url=redirect_url)
    #return templates.TemplateResponse("index.html", {"request": request, "message": message, "popular_tv_shows": popular_tv_shows})

async def add_to_archive(request):
    form_data = await request.form()
    series_id_form = form_data['series-id'] # input id of serie to be deleted
    list_id_form = form_data['list-id']
    try:
        series_id = int(series_id_form) # validate input
        list_id = int(list_id_form)
    except:
        message = "Error: Invalid input. Try again, but no tricks this time"
        return templates.TemplateResponse("index.html", {"request": request, "message": message})
    show_exists = session.query(ListEntries).filter_by(series_id=series_id, list_id=list_id).count()
    if show_exists > 0:
        session.query(ListEntries).filter_by(list_id=int(list_id), series_id=int(series_id)).update({"archive": 1}, synchronize_session='fetch')
        session.commit()
    show_name = session.query(Series.series_name).filter_by(series_id=series_id).scalar()
    session.close()
    audit_logger.info(f"ARCHIVED SHOW: {show_name} FROM IP: {request.client.host}")
    redirect_url = f"/list/{list_id}"
    return RedirectResponse(url=redirect_url)

# update_series refreshes series and episodes data. scheduler automates it.
def update_series():
    series_list = session.query(Series.series_id).all()
    # Series
    for series_tuple in series_list:
        series_id = series_tuple[0]
        sdata = try_request_series(series_id)
        edata = try_request_episodes(series_id)
        if sdata is not None:
            today = datetime.now()
            sdata_name = sdata['name']
            sdata_status = sdata['status']
            sdata_ext_thetvdb = sdata['externals'].get('thetvdb')
            sdata_ext_imdb = sdata['externals'].get('imdb')
            session.query(Series).filter(Series.series_id == series_id).update({Series.series_name: sdata_name, Series.series_status: sdata_status, Series.series_ext_thetvdb: sdata_ext_thetvdb, Series.series_ext_imdb: sdata_ext_imdb, Series.series_last_updated: today})
        # Episodes
        if edata is not None:
            # Delete old episode data
            session.query(Episodes).filter_by(ep_series_id=series_id).delete()
            session.commit()
            # Add new episode data
            add_episodes(series_id, edata)
        session.commit()
        time.sleep(45) # one should not put too much pressure on a public api
    session.close()
    logging.info("update_series success")

def download_redirect(request): # redirect old to new link
    return RedirectResponse(url=f"/subscribe/1")

def download_calendar(request):
    list_id = request.path_params['list_id']
    calendar_file_memory = io.BytesIO()
    calendar_file_memory.write(b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:nousa\nCALSCALE:GREGORIAN\n")
    # filter episodes so only episodes between one year ago and one year into the future get into the calendar
    one_year_ago = datetime.now() - timedelta(days=365)
    one_year_future = datetime.now() + timedelta(days=365)
    myshows = session.query(Series).join(ListEntries, Series.series_id == ListEntries.series_id).filter(ListEntries.list_id == list_id).all()
    myepisodes = session.query(Episodes).\
        join(ListEntries, Episodes.ep_series_id == ListEntries.series_id).\
        filter(ListEntries.list_id == list_id, ListEntries.archive == 0, Episodes.ep_airdate >= one_year_ago, Episodes.ep_airdate <= one_year_future).all()
    session.close()
    for show in myshows:
        for episode in myepisodes:
            if episode.ep_series_id == show.series_id:
                today = datetime.now()
                ep_date = episode.ep_airdate
                ep_start = ep_date + timedelta(days=1) # add one day for proper calendar event start date
                ep_end = ep_date + timedelta(days=2) # add two days for event end
                start_convert = datetime.strftime(ep_start,'%Y%m%d') # convert datetime object to string
                end_convert = datetime.strftime(ep_end,'%Y%m%d') # convert datetime object to string
                ep_nr = '{:02d}'.format(int(episode.ep_number))
                season_nr = '{:02d}'.format(int(episode.ep_season))
                
                calendar_event = (
                    "BEGIN:VEVENT\n"
                    f"DTSTAMP:{today:%Y%m%d}T{today:%H%M%S}Z\n"
                    f"DTSTART;VALUE=DATE:{start_convert}\n"
                    f"DTEND;VALUE=DATE:{end_convert}\n"
                    f"DESCRIPTION:Episode name: {episode.ep_name}\\nLast updated: {show.series_last_updated:%d-%b-%Y %H:%M}\n"
                    f"SUMMARY:{show.series_name} S{season_nr}E{ep_nr}\n"
                    f"UID:{episode.ep_id}\n"
                    "BEGIN:VALARM\n"
                    f"UID:{episode.ep_id}A\n"
                    "ACTION:DISPLAY\n"
                    f"TRIGGER;VALUE=DATE-TIME:{start_convert}T160000Z\n"
                    f"DESCRIPTION:{show.series_name} is on tv today!\n"
                    "END:VALARM\n"
                    "END:VEVENT\n"
                )
                
                calendar_file_memory.write(calendar_event.encode('utf-8'))
    calendar_file_memory.write(b"END:VCALENDAR")
    calendar_file_memory.seek(0)
    logging.info(f"success! 'download_calendar' from ip: {request.client.host}")
    headers = {'Content-Disposition': 'attachment; filename="nousa.ics"'}
    return StreamingResponse(calendar_file_memory, media_type="text/calendar", headers=headers)

async def lists_page(request):
    lists = session.query(Lists).all()
    session.close()
    return templates.TemplateResponse('lists.html', {'request': request, 'lists': lists, 'selected_lists': True})

async def list_page(request):
    list_id_path = request.path_params['list_id']
    try:
        list_id = int(list_id_path)
    except:
        return RedirectResponse(url="/")
    listentries_list = session.query(ListEntries).filter_by(list_id=list_id).all()
    lists = session.query(Lists).all()
    list_object = session.query(Lists).filter(Lists.list_id == list_id).first()
    series_array = []
    archive_array = []
    for list_item in listentries_list:
        if list_item.archive == 0:
            series_array.append(list_item.series_id)
        elif list_item.archive == 1:
            archive_array.append(list_item.series_id)
    series_list = session.query(Series).filter(Series.series_id.in_(series_array)).order_by(Series.series_status.desc())
    archive_list = session.query(Series).filter(Series.series_id.in_(archive_array)).order_by(Series.series_status.desc())
    session.close()
    return templates.TemplateResponse('list.html', {'request': request, 'listentries_list': listentries_list, 'series_list': series_list, 'archive_list': archive_list, 'list_id': list_id, 'list_object': list_object, 'lists': lists})

async def create_list(request):
    lists = session.query(Lists).all() # query data for response
    form_data = await request.form()
    user_input = form_data.get('create-list')
    name_check = session.query(Lists).filter(Lists.list_name == user_input).first()
    session.close()
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
            lists = session.query(Lists).all() # query data for response
            session.close()
            message = f"{user_input} has been created"
            audit_logger.info(f"CREATED LIST: {user_input} FROM IP: {request.client.host}")
            return templates.TemplateResponse('lists.html', {'request': request, 'message': message, 'lists': lists})
        else:
            message = "A list with that name exists already"
            return templates.TemplateResponse('lists.html', {'request': request, 'message': message, 'lists': lists})

async def rename_list(request):
    form_data = await request.form()
    list_id_form = form_data.get('list-id')
    user_input = form_data.get("rename-list")
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
    name_check = session.query(Lists).filter(Lists.list_name == user_input).count()
    if name_check > 0:
        message = "A list with that name exists already"
        return templates.TemplateResponse('index.html', {'request': request, 'message': message})
    else:
        session.query(Lists).filter_by(list_id=int(list_id)).update({"list_name": user_input}, synchronize_session='fetch')
        session.commit()
    session.close()
    return RedirectResponse(url=f"/list/{list_id}")

jobstores = {
    'default': SQLAlchemyJobStore(engine=engine)
}

scheduler = AsyncIOScheduler(jobstores=jobstores)
scheduler.start()

try: # check if job already exists in order to avoid conflict when adding job to db
    existing_job = scheduler.get_job(job_id='update_series')
    if existing_job:
        logging.info("update_series job already exists. not adding new job.")
    else:
        scheduler.add_job(
            update_series,
            trigger=CronTrigger(day_of_week='sun', hour=3, jitter=600), # job runs every Sunday around 3AM
            id='update_series',
            misfire_grace_time=86400, # if job did not run, try again if 24 hours (86400 seconds) have passed
            coalescing=True, # if multiple jobs did not run, discard all others and run only one job
        )
except ConflictingIdError as err:
    logging.error(err)

routes = [
    Route("/", endpoint=homepage, methods=["GET"]),
    Mount("/nousa", app=StaticFiles(directory="static"), name="static"),
    Route("/search", endpoint=search, methods=["GET", "POST"]),
    Route("/add_show", endpoint=add_to_series, methods=["GET", "POST"]),
    Route("/delete_show", endpoint=add_to_archive, methods=["GET", "POST"]),
    Route("/subscribe", endpoint=download_redirect, methods=["GET"]),
    Route("/create_list", endpoint=create_list, methods=["GET", "POST"]),
    Route("/rename_list", endpoint=rename_list, methods=["GET", "POST"]),
    Route("/lists", endpoint=lists_page, methods=["GET", "POST"]),
    Route("/list/{list_id}", endpoint=list_page, methods=["GET", "POST"]),
    Route("/subscribe/{list_id}", endpoint=download_calendar, methods=["GET"]),
]

app = Starlette(debug=True, routes=routes, on_startup=[db_migrations, update_series])

sess_key = secrets.token_hex()
app.add_middleware(SessionMiddleware, secret_key=sess_key, max_age=3600)
