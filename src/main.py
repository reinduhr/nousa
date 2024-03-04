from starlette.applications import Starlette
from starlette.responses import RedirectResponse, PlainTextResponse
from starlette.requests import Request
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
import requests
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, PendingRollbackError
from models import engine, Series, Episodes, SeriesArchive
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import threading
from apscheduler.triggers.cron import CronTrigger
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio

# Create SQLAlchemy session
Session = sessionmaker(bind=engine)
session = Session()

templates = Jinja2Templates(directory="templates")

async def homepage(request):
    message = ""
    return templates.TemplateResponse("index.html", {"request": request, "message": message})

async def search(request: Request):
    form = await request.form()
    series_name = form.get('seriesName')
    response = requests.get(f"https://api.tvmaze.com/search/shows?q={series_name}")
    data = response.json()
    return templates.TemplateResponse('search_result.html', {'request': request, 'data': data})

async def add_to_database(request: Request):
    form = await request.form()
    series_id = form.get("seriesId")#"seriesId" is taken from search_result.html input name value
    get_response_series = requests.get(f"https://api.tvmaze.com/shows/{series_id}")
    get_response_episodes = requests.get(f"https://api.tvmaze.com/shows/{series_id}/episodes")
    series_data = get_response_series.json()
    episodes_data = get_response_episodes.json()
    # Add series variables
    series_name = series_data.get("name")
    series_status = series_data.get("status")
    # Add TV show to database
    series = Series(series_id=int(series_id), series_name=series_name, series_status=series_status)
    try:
        session.add(series)
        session.commit()
        # Add episodes
        for element in episodes_data:
            ep_id = element.get("id")
            ep_name = element.get("name")
            ep_season = element.get("season")
            ep_number = element.get("number")
            ep_airdate = element.get("airdate")
            date_time_obj = datetime.strptime(ep_airdate, "%Y-%m-%d")
            episodes = Episodes(ep_series_id=int(series_id), ep_id=ep_id, ep_name=ep_name, ep_season=ep_season, ep_number=ep_number, ep_airdate=date_time_obj)
            session.add(episodes)
            await session.commit()
            await session.close()
            await ical_output() #create a new calendar after adding a show
        return RedirectResponse(url="/")
    except:
        return RedirectResponse(url="/")

async def my_shows(request: Request):
    try:
        myshows = session.query(Series).all()
        session.close()
        return templates.TemplateResponse('my_shows.html', {'request': request, 'myshows': myshows, 'archive_show': archive_show})
    except IntegrityError:
        return RedirectResponse(url="/series")
    except PendingRollbackError:
        session.rollback()
        return RedirectResponse(url="/series")

async def delete_series(series_id):
    session.query(Series).filter_by(series_id=series_id).delete()
    session.query(Episodes).filter_by(ep_series_id=series_id).delete()
    await session.commit()
async def archive_show(request):
    form_data = await request.form()
    series_id = form_data['show.series_id'] #input id of serie to be deleted
    
    source_show = session.query(Series).filter_by(series_id=series_id).first()
    dest_show = SeriesArchive(series_id=source_show.series_id, series_name=source_show.series_name)
    existing_series = session.query(SeriesArchive).get(series_id)#checks if series is already in archive
    if existing_series:
        pass
    else:
        session.add(dest_show)
        await session.commit()
    delete_series(series_id)
    await session.commit()
    await session.close()
    return RedirectResponse(url="/series")

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
        session.query(Series).filter(Series.series_id == series_id).update({Series.series_status: sdata_status})#WORKS!
        session.commit()
        #Episodes
        response_episodes = requests.get(f"https://api.tvmaze.com/shows/{series_id}/episodes")
        edata = response_episodes.json()
        #session.query(Episodes)
        # Add episodes
        try:
            for element in edata:
                ep_id = element.get("id")
                ep_name = element.get("name")
                ep_season = element.get("season")
                ep_number = element.get("number")
                ep_airdate = element.get("airdate")
                date_time_obj = datetime.strptime(ep_airdate, "%Y-%m-%d")
                #return PlainTextResponse(str(ep_id))
                #episodes = Episodes(ep_series_id=int(series_id), ep_id=ep_id, ep_name=ep_name, ep_season=ep_season, ep_number=ep_number, ep_airdate=date_time_obj)
                #session.add(episodes)
                #session.commit()

                existing_episode = session.query(Episodes).get(ep_id)
                #return PlainTextResponse(str(existing_episode))
                if existing_episode:
                    existing_episode.ep_name = ep_name
                    
                    existing_episode.ep_season = ep_season
                    existing_episode.ep_number = ep_number
                    existing_episode.ep_airdate = date_time_obj
                    #return PlainTextResponse(date_time_obj)
                    session.merge(existing_episode)
                    session.commit()
                    return PlainTextResponse(existing_episode.ep_name)
                else:
                    new_episode = Episodes(ep_series_id=int(series_id), ep_id=int(ep_id), ep_name=ep_name, ep_season=ep_season, ep_number=ep_number, ep_airdate=date_time_obj)
                    session.add(new_episode)
                    session.commit()
                time.sleep(30)
        except:
            continue
    session.commit()
    session.close()
    #return PlainTextResponse("success")
    #return templates.TemplateResponse("index.html", {'request': request})
#create ics file and put it in static folder
def ical_output():
    myCal = open("/code/static/calendar.ics", "wt", encoding='utf-8')
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
                    "$BEGIN:VEVENT\n"
                    f"$DTSTART;VALUE=DATE:{start_convert}\n"
                    f"$DTEND;VALUE=DATE:{end_convert}\n"
                    f"$DESCRIPTION:{episode.ep_name}\n"
                    f"$SUMMARY:{show.series_name} S{season_nr}E{ep_nr}\n"
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
                    myCal = open("/code/static/calendar.ics", "at", encoding='utf-8')
                    myCal.write(myCal_event)
                    myCal.close()
                except:
                    continue
                    #return PlainTextResponse(str("Error"))
    
    myCal = open("/code/static/calendar.ics", "at", encoding='utf-8')
    myCal.write("END:VCALENDAR")
    myCal.close()
    #return PlainTextResponse("Success!")

async def my_archive(request):
    myarchive = session.query(SeriesArchive).all()
    session.close()
    return templates.TemplateResponse("my_archive.html", {"request": request, "myarchive": myarchive})

scheduler = AsyncIOScheduler()#WORKS!
scheduler.add_job(
    update_database,
    trigger=CronTrigger(day_of_week='sun', hour=2, minute=50),
    id='update_database'
)
scheduler.add_job(
    ical_output,
    trigger=CronTrigger(day_of_week='sun', hour=4, minute=55),
    id='ical_output'
)
scheduler.start()

routes = [
    Route("/", endpoint=homepage, methods=["GET", "POST"]),
    Mount("/calendar", app=StaticFiles(directory="static"), name="static"),
    Route("/search", endpoint=search, methods=["GET", "POST"]),
    Route("/add_show", endpoint=add_to_database, methods=["GET", "POST"]),
    Route("/series", endpoint=my_shows, methods=["GET", "POST"]),
    Route("/delete_show", endpoint=archive_show, methods=["POST"]),
    Route("/archive", endpoint=my_archive, methods=["GET"]),
    #Route("/update", endpoint=test, methods=["GET", "POST", "PATCH"])
]

app = Starlette(debug=True, routes=routes)