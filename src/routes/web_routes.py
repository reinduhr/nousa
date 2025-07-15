from starlette.requests import Request
from starlette.responses import RedirectResponse
import requests
from sqlalchemy import select

from src.db import SessionLocal
from src.models import JellyfinRecommendation, Lists, ListEntries, Series
from src.services.templates import templates
from src.routes.template_data import popular_tv_shows
import logging

logger = logging.getLogger(__name__)

# a redirect to handle download link from before Lists were added
def download_redirect(request: Request):
    return RedirectResponse(url=f"/subscribe/1")

# route for home page
async def homepage(request: Request):
    with SessionLocal() as session:
        recommendations = session.scalars(select(JellyfinRecommendation)).all()
        return templates.TemplateResponse("index.html", {"request": request, "popular_tv_shows": popular_tv_shows, "recommendations": recommendations})

# route for search and search results
async def search(request: Request):
    form = await request.form()
    series_name = form.get('series-name')
    try:
        response = requests.get(f"https://api.tvmaze.com/search/shows?q={series_name}", timeout=10)
    except Exception as err:
        return templates.TemplateResponse("index.html", {"request": request, "popular_tv_shows": popular_tv_shows, "message": err})
    data = response.json()
    with SessionLocal() as session:
        lists = session.scalars(select(Lists)).all()
        return templates.TemplateResponse('search_result.html', {'request': request, 'data': data, 'lists': lists})

# route for jellyfin recommendations
async def jelly_rec(request: Request):
    with SessionLocal() as session:
        recommendations = session.scalars(select(JellyfinRecommendation)).all()
        lists = session.scalars(select(Lists)).all()
        list_entries = session.scalars(select(ListEntries)).all()
        # check if recommendation is already in list
        existing_pairs = {(entry.list_id, str(entry.series_id)) for entry in list_entries}
        return templates.TemplateResponse('jelly_rec.html', {'request': request, 'lists': lists, 'recommendations': recommendations, "existing_pairs": existing_pairs, 'selected_recs': True})

#  route for /lists
async def lists_page(request: Request):
    with SessionLocal() as session:
        lists = session.execute(select(Lists)).scalars().all()
        return templates.TemplateResponse('lists.html', {'request': request, 'lists': lists, 'selected_lists': True})

# route e.g.: /list/1
async def list_page(request: Request):
    list_id_path = request.path_params['list_id']
    try:
        list_id = int(list_id_path)
    except:
        return RedirectResponse(url="/")

    with SessionLocal() as session:
        listentries_list = session.execute(select(ListEntries).where(ListEntries.list_id == list_id)).scalars().all()
        lists = session.execute(select(Lists)).scalars().all()
        list_object = session.execute(select(Lists).where(Lists.list_id == list_id)).scalars().first()

        series_array = []
        archive_array = []
        for list_item in listentries_list:
            if list_item.archive == 0:
                series_array.append(list_item.series_id)
            elif list_item.archive == 1:
                archive_array.append(list_item.series_id)

        series_list = session.execute(select(Series).where(Series.series_id.in_(series_array)).order_by(Series.series_status.desc())).scalars().all()
        archive_list = session.execute(select(Series).where(Series.series_id.in_(archive_array)).order_by(Series.series_status.desc())).scalars().all()
        archive_count = len(archive_list)
        series_count = len(series_list)

        return templates.TemplateResponse('list.html', {'request': request, 
                                                        'listentries_list': listentries_list, 
                                                        'series_list': series_list, 
                                                        'archive_list': archive_list, 
                                                        'list_id': list_id, 
                                                        'list_object': list_object, 
                                                        'lists': lists,
                                                        'archive_count': archive_count,
                                                        'series_count': series_count
                                                    })