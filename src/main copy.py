from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse, HTMLResponse
from starlette.requests import Request
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
import requests
templates = Jinja2Templates(directory = "templates")

async def homepage(request):
    return templates.TemplateResponse('index.html', {'request': request})

async def search(request: Request):
    form = await request.form()
    series_name = form.get('seriesName')
    response = requests.get(f'https://api.tvmaze.com/search/shows?q={series_name}')
    data = response.json()
    return templates.TemplateResponse('search_result.html', {'request': request, 'data': data})

routes = [
    Route("/", endpoint=homepage),
    Mount('/calendar', app=StaticFiles(directory='static'), name="static"),
    Route("/search", endpoint=search, methods=['POST'])
]

app = Starlette(debug=True, routes=routes)