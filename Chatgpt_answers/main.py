from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.requests import Request
from starlette.templating import Jinja2Templates
import requests

app = Starlette(debug=True)
templates = Jinja2Templates(directory='templates')

@app.route('/')
async def homepage(request):
    return templates.TemplateResponse('index.html', {'request': request})

@app.route('/search', methods=['POST'])
async def search(request: Request):
    form = await request.form()
    series_name = form.get('seriesName')
    response = requests.get(f'https://api.tvmaze.com/search/shows?q={series_name}')
    data = response.json()
    return templates.TemplateResponse('search_result.html', {'request': request, 'data': data})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)