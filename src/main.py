# main.py
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.requests import Request
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
import requests
from sqlalchemy.orm import sessionmaker
from models import Series, Episodes, engine#, fetch_and_store_series
from datetime import datetime

# Create SQLAlchemy session
Session = sessionmaker(bind=engine)
session = Session()

templates = Jinja2Templates(directory="templates")

async def homepage(request):
    return templates.TemplateResponse("index.html", {"request": request})

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
    return HTMLResponse(f'Series "{series_name}" added to the database.')


"""
async def search(request: Request):
    form = await request.form()
    series_name = form.get("seriesName")
    fetch_and_store_series(series_name, session)
    return HTMLResponse(f'Series "{series_name}" added to the database.')

async def search_result(request: Request):
    form = await request.form()
    series_name = form.get("seriesName")
    response = requests.get(f"https://api.tvmaze.com/search/shows?q={series_name}")
    data = response.json()
    return templates.TemplateResponse("search_result.html", {"request": request, "data": data})
"""



routes = [
    Route("/", endpoint=homepage),
    Mount("/calendar", app=StaticFiles(directory="static"), name="static"),
    Route("/search", endpoint=search, methods=["POST"]),
    #Route("/search_result", endpoint=search_result, methods=["POST"]),
    Route("/add_to_database", endpoint=add_to_database, methods=["POST"])
]

app = Starlette(debug=True, routes=routes)
