from starlette.applications import Starlette
from starlette.responses import RedirectResponse, PlainTextResponse, FileResponse
from starlette.requests import Request
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.background import BackgroundTask
import requests
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, PendingRollbackError
from models import engine, Series, Episodes, SeriesArchive
from datetime import datetime, timedelta
from apscheduler.triggers.cron import CronTrigger
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pathlib import Path
import logging
import secrets
import aiohttp
import asyncio
from ui_data import popular_tv_shows

# Create SQLAlchemy session
Session = sessionmaker(bind=engine)
session = Session()
# Assign calendar file to variable
calendar_file = "/code/data/calendar.ics"
# Instantiating the web templates
templates = Jinja2Templates(directory="templates")
# Logging
logging.basicConfig(encoding='utf-8', level=logging.DEBUG)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
file_handler = logging.FileHandler('/code/data/nousa.log') # Create a FileHandler to log messages to a file
formatter = logging.Formatter('%(asctime)s.%(msecs)03d %(message)s', datefmt='%d-%b-%Y %H:%M:%S') # Create a formatter to specify the log message format
file_handler.setFormatter(formatter) # Set the Formatter for the FileHandler
logging.root.addHandler(file_handler) # Add the FileHandler to the root logger

async def homepage(request):
    return templates.TemplateResponse("index.html", {"request": request, "popular_tv_shows": popular_tv_shows})

async def search(request: Request):
    form = await request.form()
    series_name = form.get('seriesName')
    response = requests.get(f"https://api.tvmaze.com/search/shows?q={series_name}")
    data = response.json()
    return templates.TemplateResponse('search_result.html', {'request': request, 'data': data})

async def fetch_data(url): #asynchronous api calls. fetch multiple GET simultaneously
    async with aiohttp.ClientSession() as aiosession:
	    async with aiosession.get(url) as aioresponse:
                return await aioresponse.json()

async def add_to_database(request: Request):
    form = await request.form()
    series_id = form.get("series-id")#"series-id" is taken from search_result.html input name value
    show_exist = session.query(Series).get(series_id)
    if show_exist:
        message = "Show exists already"
        return templates.TemplateResponse("index.html", {"request": request, "message": message})
    else:
        series_url = f"https://api.tvmaze.com/shows/{series_id}"
        episode_url = f"https://api.tvmaze.com/shows/{series_id}/episodes"
        # Create tasks for fetching data from two URLs concurrently
        task1 = asyncio.create_task(fetch_data(series_url))
        task2 = asyncio.create_task(fetch_data(episode_url))
        # Wait for both tasks to complete
        series_data = await task1
        episodes_data = await task2
        # OLD REQUESTS WAY. now using aiohttp and asyncio
        #get_response_series = requests.get(f"https://api.tvmaze.com/shows/{series_id}")
        #get_response_episodes = requests.get(f"https://api.tvmaze.com/shows/{series_id}/episodes")
        #series_data = get_response_series.json()
        #episodes_data = get_response_episodes.json()
        # Add series variables
        series_name = series_data.get("name")
        series_status = series_data.get("status")
        series_ext_thetvdb = series_data["externals"].get("thetvdb")
        series_ext_imdb = series_data["externals"].get("imdb")
        # Add TV show to database
        series = Series(series_id=int(series_id), series_name=series_name, series_status=series_status, series_ext_thetvdb=series_ext_thetvdb, series_ext_imdb=series_ext_imdb)

        async def add_episodes(episodes_data): #asynchronous function which is called by BackgroundTask
            for element in episodes_data:
                ep_id = element.get("id")
                ep_name = element.get("name")
                ep_season = element.get("season")
                ep_number = element.get("number")
                ep_airdate = element.get("airdate")
                date_time_obj = datetime.strptime(ep_airdate, "%Y-%m-%d")
                episodes = Episodes(ep_series_id=int(series_id), ep_id=ep_id, ep_name=ep_name, ep_season=ep_season, ep_number=ep_number, ep_airdate=date_time_obj)
                session.add(episodes)
                session.commit()
            ical_output() #create a new calendar after adding a show

        try:
            session.add(series)
            session.commit()
            episode_task = BackgroundTask(add_episodes, episodes_data=episodes_data)
            session.close()
            logging.info('add_to_database success')
            message = f"{series_name} has been added"
            #return templates.TemplateResponse("index.html", {"request": request, "message": message})
        except IntegrityError:
            message = f"{series_name} already in My shows"
        except Exception as err:
            logging.error("add_to_database error", err)
            return templates.TemplateResponse("index.html", {"request": request, "message": err})
        return templates.TemplateResponse("index.html", {"request": request, "message": message}, background=episode_task)
        
async def my_shows(request: Request):
    try:
        myshows = session.query(Series).all()
        session.close()
        return templates.TemplateResponse('my_shows.html', {'request': request, 'myshows': myshows, 'archive_show': archive_show})#, cache_headers=False)
    except IntegrityError:
        return RedirectResponse(url="/series")
    except PendingRollbackError:
        session.rollback()
        return RedirectResponse(url="/series")

async def delete_series(series_id):
    session.query(Series).filter_by(series_id=series_id).delete()
    session.query(Episodes).filter_by(ep_series_id=series_id).delete()
    session.commit()

async def archive_show(request):
    form_data = await request.form()
    series_id = form_data['show.series_id'] #input id of serie to be deleted
    source_show = session.query(Series).get(series_id)
    info_message = source_show.series_name
    request.session["message"] = f"{info_message} was already in the archive"
    dest_show = SeriesArchive(series_id=source_show.series_id, series_name=source_show.series_name, series_status=source_show.series_status)
    existing_series = session.query(SeriesArchive).get(series_id)#checks if series is already in archive
    try:
        if not existing_series:
            session.add(dest_show)
            session.commit()
            request.session["message"] = f"{info_message} has been put into the archive"
        await delete_series(series_id)
        session.commit()
        session.close()
        logging.info("archive_show success")
        ical_output()
        #message = f"{info_message} has been put into the archive"
        message = request.session.get("message")
        myshows = session.query(Series).all() #query all shows to later display on my_shows.html
        session.close()
        return templates.TemplateResponse("my_shows.html", {"request": request, "message": message, 'myshows': myshows})
    except Exception as err:
        logging.error("archive_show error", err)
        return templates.TemplateResponse("my_shows.html", {"request": request, "message": err, 'myshows': myshows})

#update_database refreshes series and episodes data. scheduler automates it.
def update_database():
    #for every series_id in Series table get all episodes and put them in db
    series_list = session.query(Series.series_id).all()
    for series_tuple in series_list:
        series_id = series_tuple[0]
        #Series
        response_series = requests.get(f"https://api.tvmaze.com/shows/{series_id}")
        sdata = response_series.json()
        sdata_status = sdata['status']
        sdata_ext_thetvdb = sdata['externals'].get('thetvdb')
        sdata_ext_imdb = sdata['externals'].get('imdb')
        try:
            session.query(Series).filter(Series.series_id == series_id).update({Series.series_status: sdata_status, Series.series_ext_thetvdb: sdata_ext_thetvdb, Series.series_ext_imdb: sdata_ext_imdb})#WORKS!
            session.commit()
        except Exception as err:
            logging.error("error in first for loop of update_database", err)
        #Episodes
        response_episodes = requests.get(f"https://api.tvmaze.com/shows/{series_id}/episodes")
        edata = response_episodes.json()
        #Delete episodes in db before adding new. This instead of updating db records is because TVmaze sometimes deletes and adds records.
        session.query(Episodes).filter_by(ep_series_id=series_id).delete()
        # Add episodes
        try:
            for element in edata:
                ep_id = element.get("id")
                ep_name = element.get("name")
                ep_season = element.get("season")
                ep_number = element.get("number")
                ep_airdate = element.get("airdate")
                date_time_obj = datetime.strptime(ep_airdate, "%Y-%m-%d")
                
                new_episode = Episodes(ep_series_id=int(series_id), ep_id=int(ep_id), ep_name=ep_name, ep_season=ep_season, ep_number=ep_number, ep_airdate=date_time_obj)
                session.add(new_episode)
                session.commit()
        except Exception as err:
            logging.error("update_database second for loop error", err)
            continue
        time.sleep(30)
    session.commit()
    session.close()
    logging.info("update_database success")
    ical_output()

def update_archive():
    series_list = session.query(SeriesArchive.series_id).all()
    for series_tuple in series_list:
        series_id = series_tuple[0]
        response_series = requests.get(f"https://api.tvmaze.com/shows/{series_id}")
        sdata = response_series.json()
        series_status = sdata['status']
        try:
            session.query(SeriesArchive).filter(SeriesArchive.series_id == series_id).update({SeriesArchive.series_status: series_status})#WORKS!
            session.commit()
        except Exception as err:
            logging.error("error in update_archive", err)
        time.sleep(61)
    session.commit()
    session.close()
    logging.info("update_archive success")

#create ics file and put it in static folder
def ical_output():
    myCal = open(calendar_file, "wt", encoding='utf-8')
    myCal.write("BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:myCal\nCALSCALE:GREGORIAN\n")
    myCal.close()
    #filter episodes so only one year old episodes and episodes one year into the future get into the calendar
    one_year_ago = datetime.now() - timedelta(days=365)
    one_year_future = datetime.now() + timedelta(days=365)
    myepisodes = session.query(Episodes).filter(Episodes.ep_airdate >= one_year_ago, Episodes.ep_airdate <= one_year_future).all()   
    myshows = session.query(Series).all()
    for show in myshows:
        for episode in myepisodes:
            if episode.ep_series_id == show.series_id:
                ep_date = episode.ep_airdate #
                ep_start = ep_date + timedelta(days=1) #add one day for proper calendar event start date
                ep_end = ep_date + timedelta(days=2) #add two days for event end
                start_convert = datetime.strftime(ep_start,'%Y%m%d') #convert datetime object to string
                end_convert = datetime.strftime(ep_end,'%Y%m%d') #convert datetime object to string
                ep_nr = '{:02d}'.format(int(episode.ep_number))
                season_nr = '{:02d}'.format(int(episode.ep_season))
                
                myCal_event = (
                    "BEGIN:VEVENT\n"
                    f"DTSTART;VALUE=DATE:{start_convert}\n"
                    f"DTEND;VALUE=DATE:{end_convert}\n"
                    f"DESCRIPTION:{episode.ep_name}\n"
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
                try:
                    myCal = open(calendar_file, "at", encoding='utf-8')
                    myCal.write(myCal_event)
                    myCal.close()
                except Exception as err:
                    logging.error("ical_output error", err)
                    continue
    myCal = open(calendar_file, "at", encoding='utf-8')
    myCal.write("END:VCALENDAR")
    myCal.close()
    logging.info("ical_output success")

async def my_archive(request):
    myarchive = session.query(SeriesArchive).all()
    session.close()
    return templates.TemplateResponse("my_archive.html", {"request": request, "myarchive": myarchive})

async def download(request):
    file_path = Path(calendar_file)
    if file_path.is_file():
        return FileResponse(file_path, filename="calendar.ics", media_type="text/calendar")
    else:
        message = "404; Not Found"
        return templates.TemplateResponse("index.html", {"request": request, "message": message})

scheduler = AsyncIOScheduler()#WORKS!
scheduler.add_job(
    update_database,
    trigger=CronTrigger(day_of_week='sun', hour=11, minute=11),
    id='update_database'
)
scheduler.add_job(
    update_archive,
    trigger=CronTrigger(year='*', month='*', day=1, week='*', day_of_week='*', hour='4', minute=20, second=0),
    id='update_archive'
)

scheduler.start()

routes = [
    Route("/", endpoint=homepage, methods=["GET"]),
    Mount("/nousa", app=StaticFiles(directory="static"), name="static"),
    Route("/search", endpoint=search, methods=["GET", "POST"]),
    Route("/add_show", endpoint=add_to_database, methods=["GET", "POST"]),
    Route("/series", endpoint=my_shows, methods=["GET", "POST"]),
    Route("/delete_show", endpoint=archive_show, methods=["GET", "POST"]),
    Route("/archive", endpoint=my_archive, methods=["GET", "POST"]),
    Route("/subscribe", endpoint=download),
    #Route("/update", endpoint=update_database, methods=["GET", "POST", "PATCH"]),
]

app = Starlette(debug=True, routes=routes)

sess_key = secrets.token_hex()
app.add_middleware(SessionMiddleware, secret_key=sess_key, max_age=3600)