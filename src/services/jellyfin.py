import os
import logging
import aiohttp
from starlette.requests import Request

logger = logging.getLogger(__name__)

JELLYFIN_API_KEY = os.getenv("JELLYFIN_API_KEY", None)
JELLYFIN_IP = os.getenv("JELLYFIN_IP")
JELLYFIN_PORT = os.getenv("JELLYFIN_PORT")
BASE_URL = f"http://{JELLYFIN_IP}" + (f":{JELLYFIN_PORT}" if JELLYFIN_PORT else "")
HEADERS = {"X-Emby-Token": JELLYFIN_API_KEY}

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
            async with session.get(url, headers=HEADERS) as response:
                return response.status == 200
        except aiohttp.ClientError:
            return False

async def get_tv_shows():
    url = f"{BASE_URL}/Items?IncludeItemTypes=Series&Recursive=true"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as response:
            response.raise_for_status()
            data = await response.json()
            return data.get("Items", [])

async def get_episodes(show_id: str):
    url = f"{BASE_URL}/Shows/{show_id}/Episodes"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as response:
            response.raise_for_status()
            data = await response.json()
            return data.get("Items", [])

async def get_users():
    url = f"{BASE_URL}/Users"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as response:
            response.raise_for_status()
            return await response.json()

async def get_show_metadata(user_id: str, item_id: str):
    url = f"{BASE_URL}/Users/{user_id}/Items/{item_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as response:
            response.raise_for_status()
            return await response.json()

async def get_jelly_recs(request: Request):
    if await is_jellyfin_api_key_valid() and await are_services_online():
        shows = await get_tv_shows()
        users = await get_users()

        unique_shows = {}
        for show in shows:
            key = (show["Name"], show.get("PremiereDate"))
            if key not in unique_shows:
                unique_shows[key] = show
        
        shows_dict = {}
        for user in users:
            if not user:
                logger.warning("Jellyfin user not found.")
                continue

            for show in unique_shows.values():
                episodes = await get_episodes(show["Id"])
                logger.debug(f"episodes debug: {episodes}")
                if not episodes:
                    continue

                meta = await get_show_metadata(user["Id"], show["Id"])
                provider_ids = meta.get("ProviderIds", {})
                show["Imdb"] = provider_ids.get("Imdb", None)
                show["Thetvdb"] = provider_ids.get("Tvdb", None)
                show["ImgUrl"] = f"{BASE_URL}/Items/{show['Id']}/Images/Primary?X-Emby-Token={JELLYFIN_API_KEY}"
                show["Overview"] = meta.get("Overview", None)

                if show.get("Status", "Unknown") != "Ended":
                    shows_dict[show["Id"]] = show

        return shows_dict
    return {}