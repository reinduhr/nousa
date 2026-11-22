import aiohttp
from starlette.requests import Request
from starlette.responses import RedirectResponse, JSONResponse, HTMLResponse
from sqlalchemy import select, update
import logging

from src.db import SessionLocal
from src.models import Lists, ListEntries, Series
from src.services.templates import templates
from src.services.jellyfin import is_jellyfin_api_key_valid, check_jellyfin_env_vars, get_jelly_recs, get_users, exclude_series_in_list
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
        jellyfin_online = await is_jellyfin_api_key_valid()
    except Exception:
        jellyfin_online = False

    jellyfin_users = []
    if jellyfin_online:
        try:
            jellyfin_users = await get_users()
        except Exception as e:
            logger.warning(f"Could not fetch Jellyfin users: {e}")
    jellyfin_user_ids = [u["Id"] for u in jellyfin_users]

    with SessionLocal() as session:
        lists = session.scalars(select(Lists).order_by(Lists.list_id)).all()

        # selected list from ?list_id=, defaulting to the first list
        selected_list_id = None
        try:
            selected_list_id = int(request.query_params.get("list_id"))
        except (TypeError, ValueError):
            pass
        if lists and selected_list_id not in {l.list_id for l in lists}:
            selected_list_id = lists[0].list_id
        selected_list = next((l for l in lists if l.list_id == selected_list_id), None)

        list_series = []
        if selected_list is not None:
            series_ids = select(ListEntries.series_id).where(ListEntries.list_id == selected_list_id)
            list_series = session.scalars(select(Series).where(Series.series_id.in_(series_ids))).all()

    # which Jellyfin user(s) to recommend for: the user linked to the list, otherwise everyone
    linked_user_id = selected_list.jellyfin_user_id if selected_list else None
    linked_user_missing = bool(linked_user_id) and bool(jellyfin_users) and linked_user_id not in jellyfin_user_ids
    if linked_user_id and not linked_user_missing:
        rec_user_ids = [linked_user_id]
    else:
        rec_user_ids = jellyfin_user_ids

    try:
        jellyfin_series = await get_jelly_recs(rec_user_ids)
    except Exception as e:
        logger.error(f"Could not fetch Jellyfin recommendations: {e}")
        jellyfin_series = {}

    # hide recommendations that are already in the selected list (main or archive)
    if jellyfin_series and list_series:
        jellyfin_series = exclude_series_in_list(jellyfin_series, list_series)

    return templates.TemplateResponse(request, "jelly_rec.html", {
        "jellyfin_series": jellyfin_series or {},
        "check_env_vars_ok": check_env_vars_ok,
        "check_env_vars_msg": check_env_vars_msg,
        "jellyfin_online": jellyfin_online,
        "lists": lists,
        "selected_list_id": selected_list_id,
        "jellyfin_users": jellyfin_users,
        "linked_user_id": linked_user_id,
        "linked_user_missing": linked_user_missing,
        "selected_recs": True
    })

# link a nousa list to a Jellyfin user (empty value = unlink)
async def link_jellyfin_user(request: Request):
    form = await request.form()
    try:
        list_id = int(form.get("list_id"))
    except (TypeError, ValueError):
        return RedirectResponse(url="/recommendations", status_code=303)

    user_id = (form.get("jellyfin_user_id") or "").strip() or None
    if user_id is not None:
        try:
            valid_ids = {u["Id"] for u in await get_users()}
        except Exception as e:
            logger.warning(f"Could not verify Jellyfin user {user_id}: {e}")
            valid_ids = set()
        if user_id not in valid_ids:
            logger.warning(f"Refusing to link list {list_id} to unknown Jellyfin user {user_id}")
            return RedirectResponse(url=f"/recommendations?list_id={list_id}", status_code=303)

    with SessionLocal() as session:
        session.execute(update(Lists).where(Lists.list_id == list_id).values(jellyfin_user_id=user_id))
        session.commit()
    logger.info(f"List {list_id} linked to Jellyfin user {user_id or '(none)'}")
    return RedirectResponse(url=f"/recommendations?list_id={list_id}", status_code=303)

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

# route for a list (e.g.: /list/1)
async def list_page(request: Request, message: str = None, list_id: int = None):
    
    try:
        if list_id is None:
            list_id_path = request.path_params['list_id']
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
                                                        'series_count': series_count,
                                                        'message': message
                                                    })