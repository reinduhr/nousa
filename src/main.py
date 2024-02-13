from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles


async def homepage(request):
    return JSONResponse({'hoi': 'wereld'})

async def static(request):
    return JSONResponse({'hoi': 'static'})

routes = [
    Route("/", endpoint=homepage),
    Mount('/calendar', app=StaticFiles(directory='static'), name="static")
]

app = Starlette(debug=True, routes=routes)