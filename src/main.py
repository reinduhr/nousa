from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.responses import PlainTextResponse
from starlette.responses import HTMLResponse
from starlette.routing import Route
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from myCal_dictionary import myCal_dictionary

async def homepage(request):
    return JSONResponse(content=myCal_dictionary)

routes = [
    Route("/", endpoint=homepage),
    Mount('/calendar', app=StaticFiles(directory='static'), name="static")
]

app = Starlette(debug=True, routes=routes)