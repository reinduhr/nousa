import time
import os
import logging
import requests
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from urllib.parse import urljoin

from src.db import SessionLocal
from src.models import JellyfinRecommendation

logger = logging.getLogger(__name__)

JELLYFIN_API_KEY = os.getenv("JELLYFIN_API_KEY")
JELLYFIN_IP = os.getenv("JELLYFIN_IP")
JELLYFIN_PORT = os.getenv("JELLYFIN_PORT")
BASE_URL = f"http://{JELLYFIN_IP}" + (f":{JELLYFIN_PORT}" if JELLYFIN_PORT else "")
HEADERS = {"X-Emby-Token": JELLYFIN_API_KEY}

def is_service_online(name: str, url: str, timeout: int = 5) -> bool:
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except requests.RequestException as e:
        logger.warning(f"{name} check failed:", e)
        return False

def are_services_online() -> bool:
    tvmaze_ok = is_service_online("TVmaze", "https://api.tvmaze.com/shows/1")
    jellyfin_ok = is_service_online("Jellyfin", BASE_URL) if BASE_URL else False

    return tvmaze_ok and jellyfin_ok

def is_jellyfin_api_key_valid() -> bool:
    url = f"{BASE_URL}/Users"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return True
    else:
        return False

def get_tv_shows():
    url = f"{BASE_URL}/Items?IncludeItemTypes=Series&Recursive=true"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json().get("Items", [])

def get_episodes(show_id: str):
    url = f"{BASE_URL}/Shows/{show_id}/Episodes"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json().get("Items", [])

def get_users():
    url = f"{BASE_URL}/Users"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()

def get_show_metadata(user_id: str, item_id: str):
    url = f"{BASE_URL}/Users/{user_id}/Items/{item_id}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()

def lookup_tvmaze(imdb: str = None, thetvdb: str = None):
    if imdb:
        url = f"https://api.tvmaze.com/lookup/shows?imdb={imdb}"
    elif thetvdb:
        url = f"https://api.tvmaze.com/lookup/shows?thetvdb={thetvdb}"
    else:
        return None

    response = requests.get(url, allow_redirects=True)
    if response.status_code == 200:
        return response.json()
    return None

def update_recommendations():
    if is_jellyfin_api_key_valid():
        if are_services_online():
            with SessionLocal() as session:

                session.execute(delete(JellyfinRecommendation))
                session.commit()

                shows = get_tv_shows()
                users = get_users()
                
                unique_shows = {}
                for show in shows:
                    key = (show["Name"], show.get("PremiereDate"))
                    if key not in unique_shows:
                        unique_shows[key] = show
                    
                for user in users:
                    
                    if not user:
                        logger.warning("Jellyfin user not found.")
                        continue
                    
                    for show in unique_shows.values():
                        episodes = get_episodes(show["Id"])
                        logger.debug("episodes debug:", episodes)
                        if not episodes:
                            continue
                        if show["Status"] != "Ended":
                            meta = get_show_metadata(user["Id"], show["Id"])
                            provider_ids = meta.get("ProviderIds", {})
                            imdb = provider_ids.get("Imdb")
                            thetvdb = provider_ids.get("Tvdb")
                            tvmaze_data = lookup_tvmaze(imdb, thetvdb)
                            time.sleep(300)
                            if not tvmaze_data:
                                continue
                            if tvmaze_data["status"] == "Ended":
                                continue
                        
                            existing = session.execute(
                                select(JellyfinRecommendation).where(
                                    JellyfinRecommendation.series_id == tvmaze_data["id"]
                                )
                            ).scalar_one_or_none()

                            if existing:
                                continue
                                
                            try:
                                rec = JellyfinRecommendation(
                                    series_id=tvmaze_data["id"],
                                    series_ext_imdb=imdb,
                                    series_ext_thetvdb=thetvdb,
                                    series_name=tvmaze_data["name"],
                                    year_start=int(tvmaze_data.get("premiered", "0")[:4]),
                                    year_end=int(tvmaze_data.get("ended", "0")[:4]) if tvmaze_data.get("ended") else None,
                                    status=tvmaze_data["status"],
                                    description=tvmaze_data["summary"],
                                    url_img_medium=urljoin(BASE_URL, f"/Items/{show['Id']}/Images/Primary?X-Emby-Token={JELLYFIN_API_KEY}")
                                )
                                session.add(rec)
                                
                            except IntegrityError as err:
                                logger.error("Jellyfin Integrity Error:", err)
                                session.rollback()
                                continue

                            except Exception as err:
                                logger.error("Jellyfin refresh error:", err)
                                session.rollback()
                                continue

                        session.commit()