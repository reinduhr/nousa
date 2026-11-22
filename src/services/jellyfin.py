import os
import logging
import aiohttp

logger = logging.getLogger(__name__)

JELLYFIN_API_KEY = os.getenv("JELLYFIN_API_KEY", None)
JELLYFIN_IP = os.getenv("JELLYFIN_IP")
JELLYFIN_PORT = os.getenv("JELLYFIN_PORT")
BASE_URL = f"http://{JELLYFIN_IP}" + (f":{JELLYFIN_PORT}" if JELLYFIN_PORT else "")

def get_headers():
    api_key = os.getenv("JELLYFIN_API_KEY")
    return {
        "Authorization": f'MediaBrowser Token="{api_key}", Client="nousa"',
        "Content-Type": "application/json"
    }

def check_jellyfin_env_vars():
    required_vars = ["JELLYFIN_API_KEY", "JELLYFIN_IP", "JELLYFIN_PORT"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        return False, f"Missing environment variables: {', '.join(missing)}"
    return True, "All Jellyfin environment variables are set"

async def is_service_online(name: str, url: str, timeout: int = 5) -> bool:
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=timeout) as response:
                return response.status == 200
        except aiohttp.ClientError as e:
            logger.warning(f"{name} check failed: {e}")
            return False

async def are_services_online() -> bool:
    if not BASE_URL:
        return False
    return await is_service_online("Jellyfin", BASE_URL)

async def is_jellyfin_api_key_valid() -> bool:
    url = f"{BASE_URL}/Users"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=get_headers()) as response:
                return response.status == 200
        except aiohttp.ClientError:
            return False

async def get_users():
    url = f"{BASE_URL}/Users"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers()) as response:
            response.raise_for_status()
            return await response.json()

async def get_user_series(session: aiohttp.ClientSession, user_id: str) -> list:
    """All series this Jellyfin user can see, incl. provider ids, overview and episode count."""
    url = (f"{BASE_URL}/Users/{user_id}/Items?IncludeItemTypes=Series&Recursive=true"
           f"&Fields=ProviderIds,Overview,RecursiveItemCount")
    async with session.get(url, headers=get_headers()) as response:
        if response.status in (400, 404):
            logger.warning(f"Jellyfin user {user_id} not found, skipping.")
            return []
        response.raise_for_status()
        data = await response.json()
        return data.get("Items", [])

def _norm_tvdb(value) -> str:
    """Normalize a TheTVDB id: nousa stores an int, Jellyfin returns a string."""
    if value in (None, ""):
        return ""
    return str(value).strip()

def exclude_series_in_list(recommendations: dict, list_series) -> dict:
    """
    Remove Jellyfin recommendations that already exist in a nousa list,
    matched on TheTVDB id. `list_series` is an iterable of Series rows.
    """
    tvdb_ids = {_norm_tvdb(s.series_ext_thetvdb) for s in list_series} - {""}

    filtered = {}
    for rec_id, rec in recommendations.items():
        tvdb = _norm_tvdb(rec.get("Thetvdb"))
        if tvdb and tvdb in tvdb_ids:
            logger.debug(f"Excluding recommendation '{rec.get('Name')}' (tvdb={tvdb}): already in list")
            continue
        logger.debug(f"Keeping recommendation '{rec.get('Name')}' (tvdb={tvdb or '-'})")
        filtered[rec_id] = rec
    logger.info(f"Recommendations: {len(recommendations)} from Jellyfin, "
                f"{len(recommendations) - len(filtered)} hidden because already in list "
                f"({len(list_series)} series in list)")
    return filtered

async def get_jelly_recs(user_ids) -> dict:
    """
    Recommendations = series in Jellyfin that are not ended and have episodes,
    limited to what the given Jellyfin users can see. Returns {jellyfin_item_id: show}.
    """
    if not user_ids or not (await is_jellyfin_api_key_valid() and await are_services_online()):
        return {}

    seen = set()
    shows_dict = {}
    async with aiohttp.ClientSession() as session:
        for user_id in user_ids:
            for show in await get_user_series(session, user_id):
                # the same show can exist in several libraries
                key = (show["Name"], show.get("PremiereDate"))
                if key in seen:
                    continue
                if show.get("Status", "Unknown") == "Ended" or not show.get("RecursiveItemCount"):
                    continue
                seen.add(key)

                provider_ids = show.get("ProviderIds") or {}
                show["Imdb"] = provider_ids.get("Imdb")
                show["Thetvdb"] = provider_ids.get("Tvdb")
                show["ImgUrl"] = f"{BASE_URL}/Items/{show['Id']}/Images/Primary?ApiKey={JELLYFIN_API_KEY}"
                shows_dict[show["Id"]] = show

    logger.info(f"Recommendations: {len(shows_dict)} series for Jellyfin user(s) {', '.join(user_ids)}")
    return shows_dict
