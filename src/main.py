from starlette.applications import Starlette
from starlette.responses import RedirectResponse, FileResponse
from starlette.requests import Request
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.background import BackgroundTask
import requests
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, PendingRollbackError
from .models import engine, Series, Episodes, SeriesArchive
from datetime import datetime, timedelta
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.base import ConflictingIdError
from pathlib import Path
import time
import logging
import secrets
import aiohttp
import asyncio
from .ui_data import popular_tv_shows
import subprocess

async def db_migrations():
    result = subprocess.run(["alembic", "upgrade", "head"], capture_output=True, text=True)
    if result.returncode != 0:
        logging.error(f"Alembic database migrations failed: {result.stderr}")

# Create SQLAlchemy session
Session = sessionmaker(bind=engine)
session = Session()
# Assign calendar file to variable
calendar_file = "/code/data/nousa.ics"
# Instantiating the web templates
templates = Jinja2Templates(directory="templates")
# Logging
logging.basicConfig(encoding='utf-8', level=logging.DEBUG)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
file_handler = logging.FileHandler('/code/data/nousa.log') # Create a FileHandler to log messages to a file
formatter = logging.Formatter('%(asctime)s.%(msecs)03d %(message)s', datefmt='%d-%b-%Y %H:%M:%S') # Create a formatter to specify the log message format
file_handler.setFormatter(formatter) # Set the Formatter for the FileHandler
logging.root.addHandler(file_handler) # Add the FileHandler to the root logger. root logger has most permissions

async def homepage(request): # /
    return templates.TemplateResponse("index.html", {"request": request, "popular_tv_shows": popular_tv_shows})

async def my_shows(request: Request): # /series
    try:
        myshows = session.query(Series).order_by(Series.series_status.desc()).all()
        session.close()
        return templates.TemplateResponse('my_shows.html', {'request': request, 'myshows': myshows, 'archive_show': archive_show, 'selected_series': True})
    except IntegrityError:
        return RedirectResponse(url="/series")
    except PendingRollbackError:
        session.rollback()
        return RedirectResponse(url="/series")

async def my_archive(request): # /archive
    myarchive = session.query(SeriesArchive).order_by(SeriesArchive.series_status.desc()).all()
    session.close()
    return templates.TemplateResponse("my_archive.html", {"request": request, "myarchive": myarchive, 'selected_archive': True})

async def download(request): # /subscribe
    file_path = Path(calendar_file)
    if file_path.is_file():
        return FileResponse(file_path, filename="nousa.ics", media_type="text/calendar")
    else:
        message = "404 Not Found"
        return templates.TemplateResponse("index.html", {"request": request, "message": message, "popular_tv_shows": popular_tv_shows})

async def search(request: Request):
    form = await request.form()
    series_name = form.get('series-name')
    try:
        response = requests.get(f"https://api.tvmaze.com/search/shows?q={series_name}", timeout=10)
    except Exception as err:
        return templates.TemplateResponse("index.html", {"request": request, "popular_tv_shows": popular_tv_shows, "message": err})
    data = response.json()
    return templates.TemplateResponse('search_result.html', {'request': request, 'data': data})

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

async def add_to_database(request: Request):
    form = await request.form()
    series_id_form = form.get("series-id") # "series-id" is taken from search_result.html input name value
    try:
        series_id = int(series_id_form) # validate input
    except:
        message = "Error: Invalid input. Try again, but no tricks this time"
        return templates.TemplateResponse("index.html", {"request": request, "message": message, "popular_tv_shows": popular_tv_shows})
    show_exist = session.query(Series).get(series_id)
    if show_exist:
        message = f"{show_exist.series_name} exists already"
        return templates.TemplateResponse("index.html", {"request": request, "message": message, "popular_tv_shows": popular_tv_shows})
    else:
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
        today = datetime.now()
        # Add TV show to database
        series = Series(series_id=int(series_id), series_name=series_name, series_status=series_status, series_ext_thetvdb=series_ext_thetvdb, series_ext_imdb=series_ext_imdb, series_last_updated=today)
        try:
            session.add(series)
            session.commit()
            episode_task = BackgroundTask(add_episodes, series_id=series_id, edata=edata)
            session.close()
            logging.info(f"{series_name} has been added")
            message = f"{series_name} has been added"
            # run ical output job 2 minutes from moment of adding show to make sure it runs AFTER BackgroundTask
            try: # check if job already exists in order to avoid conflict when adding job to db
                existing_job = scheduler.get_job(job_id='ical_output')
                if existing_job:
                    logging.info("ical_output job already exists. not adding new job.")
                else:
                    scheduler.add_job(
                        ical_output,
                        trigger=DateTrigger(run_date=datetime.now() + timedelta(seconds=20)),
                        id='ical_output',
                        misfire_grace_time=600,
                        coalescing=True,
                    )
            except ConflictingIdError as err:
                logging.error(err)
        except Exception as err:
            logging.error("add_to_database error:", err)
            return templates.TemplateResponse("index.html", {"request": request, "message": err, "popular_tv_shows": popular_tv_shows})
        return templates.TemplateResponse("index.html", {"request": request, "message": message, "popular_tv_shows": popular_tv_shows}, background=episode_task)

async def delete_series(series_id):
    session.query(Series).filter_by(series_id=series_id).delete()
    session.query(Episodes).filter_by(ep_series_id=series_id).delete()
    session.commit()

async def archive_show(request):
    myshows = session.query(Series).all() # query all shows to later display on my_shows.html
    session.close()
    form_data = await request.form()
    series_id_form = form_data['show.series_id'] # input id of serie to be deleted
    try:
        series_id = int(series_id_form) # validate input
    except:
        message = "Error: Invalid input. Try again, but no tricks this time"
        return templates.TemplateResponse("my_shows.html", {"request": request, "message": message, 'myshows': myshows})
    source_show = session.query(Series).get(series_id)
    info_message = source_show.series_name
    message = f"{info_message} was already in the archive"
    dest_show = SeriesArchive(series_id=source_show.series_id, series_name=source_show.series_name, series_status=source_show.series_status, series_last_updated=source_show.series_last_updated)
    existing_series = session.query(SeriesArchive).get(series_id) # checks if series is already in archive
    try:
        if not existing_series:
            session.add(dest_show)
            session.commit()
            message = f"{info_message} has been put into the archive"
        await delete_series(series_id)
        session.commit()
        session.close()
        logging.info("archive_show success")
        ical_output()
        myshows = session.query(Series).all() # query all shows to later display on my_shows.html
        session.close()
        return templates.TemplateResponse("my_shows.html", {"request": request, "message": message, 'myshows': myshows})
    except Exception as err:
        logging.error("archive_show error", err)
        session.close()
        return templates.TemplateResponse("my_shows.html", {"request": request, "message": err, 'myshows': myshows})

# update_series refreshes series and episodes data. scheduler automates it.
def update_series():
    series_list = session.query(Series.series_id).all()
    # Series
    for series_tuple in series_list:
        series_id = series_tuple[0]
        sdata = try_request_series(series_id)
        edata = try_request_episodes(series_id)
        #logging.error(edata)
        if sdata is not None:
            sdata_status = sdata['status']
            sdata_ext_thetvdb = sdata['externals'].get('thetvdb')
            sdata_ext_imdb = sdata['externals'].get('imdb')
            today = datetime.now()
            session.query(Series).filter(Series.series_id == series_id).update({Series.series_status: sdata_status, Series.series_ext_thetvdb: sdata_ext_thetvdb, Series.series_ext_imdb: sdata_ext_imdb, Series.series_last_updated: today})
            session.commit()
        # Episodes
        if edata is not None:
            # Delete old episode data
            session.query(Episodes).filter_by(ep_series_id=series_id).delete()
            session.commit()
            # Add new episode data
            add_episodes(series_id, edata)
            session.commit()
        time.sleep(30)
    session.commit()
    session.close()
    logging.info("update_series success")
    ical_output()

def update_archive():
    series_list = session.query(SeriesArchive.series_id).all()
    for series_tuple in series_list:
        series_id = series_tuple[0]
        sdata = try_request_series(series_id)
        if sdata is not None:
            series_status = sdata['status']
            today = datetime.now()
            session.query(SeriesArchive).filter(SeriesArchive.series_id == series_id).update({SeriesArchive.series_status: series_status, SeriesArchive.series_last_updated: today})
            session.commit()
            time.sleep(61)
    session.close()
    logging.info("update_archive success")

# create ics file and put it in static folder
def ical_output():
    calendar = open(calendar_file, "wt", encoding='utf-8')
    calendar.write("BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:nousa\nCALSCALE:GREGORIAN\n")
    calendar.close()
    # filter episodes so only one year old episodes and episodes one year into the future get into the calendar
    one_year_ago = datetime.now() - timedelta(days=365)
    one_year_future = datetime.now() + timedelta(days=365)
    today = datetime.now()
    myepisodes = session.query(Episodes).filter(Episodes.ep_airdate >= one_year_ago, Episodes.ep_airdate <= one_year_future).all()   
    myshows = session.query(Series).all()
    for show in myshows:
        for episode in myepisodes:
            if episode.ep_series_id == show.series_id:
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
                    f"DESCRIPTION:Episode name: {episode.ep_name}\\nLast updated: {show.series_last_updated:%d-%b-%Y %H:%M}\n" if show.series_last_updated else f"DESCRIPTION:Episode name: {episode.ep_name}\n"
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
                
                calendar = open(calendar_file, "at", encoding='utf-8')
                calendar.write(calendar_event)
                calendar.close()
    calendar = open(calendar_file, "at", encoding='utf-8')
    calendar.write("END:VCALENDAR")
    calendar.close()
    logging.info("ical_output success")

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

try: # check if job already exists in order to avoid conflict when adding job to db
    existing_job = scheduler.get_job(job_id='update_archive')
    if existing_job:
        logging.info("update_series job already exists. not adding new job.")
    else:
        scheduler.add_job(
            update_archive,
            trigger=CronTrigger(year='*', month='*', day=1, week='*', day_of_week='*', hour='3', jitter=600),
            id='update_archive',
            misfire_grace_time=86400,
            coalescing=True,
        )
except ConflictingIdError as err:
    logging.error(err)

routes = [
    Route("/", endpoint=homepage, methods=["GET"]),
    Mount("/nousa", app=StaticFiles(directory="static"), name="static"),
    Route("/search", endpoint=search, methods=["GET", "POST"]),
    Route("/add_show", endpoint=add_to_database, methods=["GET", "POST"]),
    Route("/series", endpoint=my_shows, methods=["GET", "POST"]),
    Route("/delete_show", endpoint=archive_show, methods=["GET", "POST"]),
    Route("/archive", endpoint=my_archive, methods=["GET", "POST"]),
    Route("/subscribe", endpoint=download),
]

app = Starlette(debug=True, routes=routes, on_startup=[db_migrations])

sess_key = secrets.token_hex()
app.add_middleware(SessionMiddleware, secret_key=sess_key, max_age=3600)