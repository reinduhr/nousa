import aiohttp
from starlette.requests import Request
from starlette.responses import RedirectResponse, JSONResponse, HTMLResponse
from sqlalchemy import select
import logging

from src.db import SessionLocal
from src.models import Lists, ListEntries, Series
from src.services.templates import templates
from src.services.jellyfin import is_jellyfin_api_key_valid, check_jellyfin_env_vars, get_jelly_recs
from src.routes.template_data import popular_tv_shows
from src.cal_logic.input import build_available_lists

logger = logging.getLogger(__name__)

# a redirect to handle download link from before Lists were added
def download_redirect(request: Request):
    return RedirectResponse(url=f"/subscribe/1")

# route for home page
async def homepage(request: Request):
    return templates.TemplateResponse(request, "index.html", {"popular_tv_shows": popular_tv_shows})

# route for jellyfin recommendations (async)
async def jellyrec(request: Request):
    check_env_vars_ok, check_env_vars_msg = check_jellyfin_env_vars()
    try:
        jellyfin_online = await is_jellyfin_api_key_valid()  # Await the async function
    except Exception:
        jellyfin_online = False
    jellyfin_series = await get_jelly_recs(request)  # Await the async function
    if jellyfin_series:
        return templates.TemplateResponse(request, "jelly_rec.html", {
            "jellyfin_series": jellyfin_series, 
            "check_env_vars_ok": check_env_vars_ok,
            "check_env_vars_msg": check_env_vars_msg,
            "jellyfin_online": jellyfin_online
        })
    # Optionally handle the case when jellyfin_series is empty
    return templates.TemplateResponse(request, "jelly_rec.html", {
        "jellyfin_series": {},
        "check_env_vars_ok": check_env_vars_ok,
        "check_env_vars_msg": check_env_vars_msg,
        "jellyfin_online": jellyfin_online
    })

# route for search and search results
async def search(request: Request):
    form = await request.form()
    series_name = form.get('series-name')
    search_term = request.query_params.get("q")
    if search_term:
        series_name = search_term

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"https://api.tvmaze.com/search/shows?q={series_name}", timeout=10
            ) as response:
                response.raise_for_status()
                data = await response.json()
        except aiohttp.ClientError as err:
            return templates.TemplateResponse(
                request, 
                "index.html",
                {
                    "popular_tv_shows": popular_tv_shows,
                    "message": f"Error fetching TV shows: {err}",
                },
            )

    with SessionLocal() as session:
        lists = session.scalars(select(Lists)).all()
        list_entries = session.scalars(select(ListEntries)).all()
        
        available_lists_for_show = build_available_lists(lists, list_entries)

        return templates.TemplateResponse(
            request, 
            'search_result.html',
            {
                'data': data,
                'available_lists_for_show': available_lists_for_show,
                'lists': lists
            }
        )

#  route for /lists
async def lists_page(request: Request):
    with SessionLocal() as session:
        lists = session.execute(select(Lists)).scalars().all()
        return templates.TemplateResponse(request, 'lists.html', {'lists': lists, 'selected_lists': True})

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

        return templates.TemplateResponse(request, 'list.html', {
                                                        'listentries_list': listentries_list, 
                                                        'series_list': series_list, 
                                                        'archive_list': archive_list, 
                                                        'list_id': list_id, 
                                                        'list_object': list_object, 
                                                        'lists': lists,
                                                        'archive_count': archive_count,
                                                        'series_count': series_count
                                                    })