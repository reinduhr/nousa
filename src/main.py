from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.responses import PlainTextResponse
from starlette.responses import HTMLResponse
from starlette.routing import Route
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
           
templates = Jinja2Templates(directory = "templates")

async def homepage(request):
    return templates.TemplateResponse(request, 'index.html')

routes = [
    Route("/", endpoint=homepage),
    Mount('/calendar', app=StaticFiles(directory='static'), name="static")
]

app = Starlette(debug=True, routes=routes)