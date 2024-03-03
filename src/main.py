from starlette.applications import Starlette
from starlette.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from starlette.requests import Request
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
import requests
from sqlalchemy.orm import sessionmaker
from models import engine, Series, Episodes, SeriesArchive
from datetime import datetime

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
    if int(series_id) not in Series.series_id:
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
            session.commit()
            return RedirectResponse(url="/")
    else:
        return RedirectResponse(url="/")

async def my_shows(request: Request):
    myshows = session.query(Series).all()
    return templates.TemplateResponse('my_shows.html', {'request': request, 'myshows': myshows, 'archive_show': archive_show})

def delete_series(series_id):
    session.query(Series).filter_by(series_id=series_id).delete()
    session.query(Episodes).filter_by(ep_series_id=series_id).delete()
    session.commit()

async def archive_show(request):
    form_data = await request.form()
    series_id = form_data['show.series_id'] #input id of serie to be deleted
    
    source_show = session.query(Series).filter_by(series_id=series_id).first()
    #source_episodes = session.query(Episodes).filter_by(ep_series_id=series_id).all()
    dest_show = SeriesArchive(series_id=source_show.series_id, series_name=source_show.series_name)
    show_lookup = session.query(SeriesArchive).filter_by(series_id=series_id).first()
    #return PlainTextResponse(str(dest_show.series_id))
    session.add(dest_show)
    session.commit()
    return RedirectResponse(url="/my_shows")
    
routes = [
    Route("/", endpoint=homepage),
    Mount("/calendar", app=StaticFiles(directory="static"), name="static"),
    Route("/search", endpoint=search, methods=["GET", "POST"]),
    Route("/add_to_database", endpoint=add_to_database, methods=["GET", "POST"]),
    Route("/my_shows", endpoint=my_shows, methods=["GET", "POST"]),
    Route("/delete_show", endpoint=archive_show, methods=["POST"])
]

app = Starlette(debug=True, routes=routes)