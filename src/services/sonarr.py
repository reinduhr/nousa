import logging
import os
from typing import List, Dict, Optional, Iterable, Tuple, Set, Any
import requests
import time
import json

from sqlalchemy import select

from src.db import SessionLocal
from src.models import AuditLogEntry, ListEntries, Series

logger = logging.getLogger(__name__)

def parse_allowed_list(raw: Optional[str]) -> List[int]:
    if not raw:
        return []
    raw = raw.strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [int(x) for x in parsed]
    except Exception:
        pass
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return [int(p) for p in parts]

SONARR_API_KEY = os.getenv("SONARR_API_KEY")
SONARR_URL = os.getenv("SONARR_URL")
if SONARR_URL:
    SONARR_URL = SONARR_URL.rstrip("/")
SONARR_ROOTFOLDER = os.getenv("SONARR_ROOTFOLDER", None)
SONARR_QUALITYPROFILE = int(os.getenv("SONARR_QUALITYPROFILE", "1"))
# parse monitored env var to boolean
_monitored_raw = os.getenv("SONARR_MONITORED", "true").lower()
SONARR_MONITORED = _monitored_raw in ("1", "true", "yes", "y", "on")
env_value = os.getenv("NOUSA_ALLOWED_LIST")
NOUSA_ALLOWED_LIST = parse_allowed_list(env_value) if env_value else None

if not SONARR_API_KEY:
    logger.warning("SONARR_API_KEY not set — Sonarr calls will fail until configured.")

if not SONARR_URL:
    logger.warning("SONARR_URL not set — Sonarr calls will fail until configured.")


class SonarrClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 10):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "X-Api-Key": self.api_key,
            "User-Agent": "nousa-sonarr-sync/1.0"
        })

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def ping(self) -> bool:
        if not self.base_url:
            logger.debug("Sonarr base URL not provided.")
            return False
        try:
            r = self._session.get(self._url("/api/v3/system/status"), timeout=self.timeout)
            r.raise_for_status()
            return True
        except Exception as e:
            logger.debug("Sonarr ping failed: %s", e)
            return False

    def get_sonarr_rootfolder(self) -> Optional[dict]:
        # prefer env override
        if SONARR_ROOTFOLDER:
            logger.info("Using SONARR_ROOTFOLDER from environment: %s", SONARR_ROOTFOLDER)
            return {"path": SONARR_ROOTFOLDER}

        if not self.base_url:
            return None
        try:
            r = self._session.get(self._url("/api/v3/rootfolder"), timeout=self.timeout)
            r.raise_for_status()
            folders = r.json()
            if not folders:
                logger.warning("No root folders found in Sonarr.")
                return None
            best = max(folders, key=lambda f: f.get("freeSpace", 0))
            return best
        except Exception as e:
            logger.exception("Failed to fetch root folders: %s", e)
            return None

    def get_all_series(self) -> List[dict]:
        if not self.base_url:
            return []
        try:
            r = self._session.get(self._url("/api/v3/series"), timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.exception("Failed to fetch series from Sonarr: %s", e)
            return []

    def add_series(self, series_name: str, tvdb_id: int, root_folder: str,
                   quality_profile_id: int, language_profile_id: Optional[int] = None,
                   series_type: str = "standard", season_folder: bool = True,
                   monitored: bool = True, search_for_missing: bool = False) -> Optional[dict]:
        if not self.base_url:
            logger.warning("Cannot add series: Sonarr base URL not set")
            return None
        payload = {
            "title": series_name,
            "tvdbId": int(tvdb_id),
            # Sonarr expects rootFolderPath and path; path usually rootFolderPath + /Title
            "rootFolderPath": root_folder,
            "path": f"{root_folder}/{series_name}" if root_folder else f"/{series_name}",
            "qualityProfileId": int(quality_profile_id),
            "monitored": bool(monitored),
            "monitorNewItems": "all",
        }
        if language_profile_id is not None:
            payload["languageProfileId"] = int(language_profile_id)
        # optional fields
        payload["seriesType"] = series_type
        payload["seasonFolder"] = bool(season_folder)

        try:
            r = self._session.post(self._url("/api/v3/series"), json=payload, timeout=self.timeout)
            if r.status_code in (200, 201):
                logger.info("Added %s (tvdb %s) to Sonarr", series_name, tvdb_id)
                return r.json()
            else:
                # Sonarr often returns 400 with JSON errors
                logger.warning("Failed to add %s (tvdb %s) -> %s: %s", series_name, tvdb_id, r.status_code, r.text)
                return None
        except Exception as e:
            logger.exception("Exception while adding series to Sonarr: %s", e)
            return None

    def delete_series(self, sonarr_series_id: int, delete_files: bool = False, add_exclusion: bool = False) -> bool:
        if not self.base_url:
            logger.warning("Cannot delete series: Sonarr base URL not set")
            return False
        params = {"deleteFiles": "true" if delete_files else "false", "addImportExclusion": "true" if add_exclusion else "false"}
        try:
            r = self._session.delete(self._url(f"/api/v3/series/{sonarr_series_id}"), params=params, timeout=self.timeout)
            if r.status_code in (200, 204):
                logger.info("Deleted Sonarr series id %s", sonarr_series_id)
                return True
            else:
                logger.warning("Failed to delete Sonarr series id %s -> %s: %s", sonarr_series_id, r.status_code, r.text)
                return False
        except Exception as e:
            logger.exception("Exception while deleting series from Sonarr: %s", e)
            return False


def get_nousa_series_all(allowed_list: Optional[Iterable[int]] = None) -> List[Tuple[int, str, Optional[int]]]:
    with SessionLocal() as session:
        stmt = select(Series.series_id, Series.series_name, Series.series_ext_thetvdb).join(
            ListEntries, Series.series_id == ListEntries.series_id
        ).where(ListEntries.archive == 0)

        if allowed_list:
            stmt = stmt.where(ListEntries.list_id.in_(list(allowed_list)))

        rows = session.execute(stmt).all()
        # SQLAlchemy row objects may be Row or tuple; normalize to tuples
        normalized = []
        for r in rows:
            # r may be Row; tuple(r) will give values
            try:
                vals = tuple(r)
            except Exception:
                vals = (r.series_id, r.series_name, r.series_ext_thetvdb)
            normalized.append(vals)
        return normalized


def get_nousa_map_tvdb_to_name(rows: Iterable[Tuple[int, str, Optional[int]]]) -> Dict[int, str]:
    tvdb_map: Dict[int, str] = {}
    for series_id, series_name, tvdb in rows:
        if tvdb is None:
            continue
        try:
            tid = int(tvdb)
        except (TypeError, ValueError):
            continue
        if tid not in tvdb_map:
            tvdb_map[tid] = series_name or f"tvdb-{tid}"
    logger.debug("nousa tvdb->name map: %s", tvdb_map)
    return tvdb_map


def get_nousa_tvmaze_ids(rows: Iterable[Tuple[int, str, Optional[int]]]) -> Set[int]:
    tvmaze_ids: Set[int] = set()
    for series_id, series_name, tvdb in rows:
        if series_id is None:
            continue
        try:
            tvmz = int(series_id)
        except (TypeError, ValueError):
            continue
        tvmaze_ids.add(tvmz)
    logger.debug("nousa tvmaze ids: %s", sorted(tvmaze_ids))
    return tvmaze_ids


def _get_sonarr_map_tvmaze_to_sonarrid() -> Dict[int, int]:
    client = SonarrClient(SONARR_URL, SONARR_API_KEY)
    series = client.get_all_series()
    mapping: Dict[int, int] = {}
    for s in series:
        sonarr_id = s.get("id")
        tvmz = s.get("tvMazeId") or s.get("tvmazeId") or s.get("tvMazeID") or s.get("tvmaze_id")
        if tvmz is None or sonarr_id is None:
            continue
        try:
            mapping[int(tvmz)] = int(sonarr_id)
        except Exception:
            continue
    return mapping


def _get_sonarr_map_tvdb_to_sonarrid() -> Dict[int, Dict[str, Any]]:
    client = SonarrClient(SONARR_URL, SONARR_API_KEY)
    series = client.get_all_series()
    mapping: Dict[int, Dict[str, Any]] = {}
    for s in series:
        sonarr_id = s.get("id")
        tvdb = s.get("tvdbId")
        name = s.get("title")
        if tvdb is None or sonarr_id is None:
            continue
        try:
            mapping[int(tvdb)] = {
                "sonarr_id": int(sonarr_id),
                "series_name": name or "Unknown"
            }
        except Exception:
            continue
    return mapping


def is_sonarr_online() -> bool:
    client = SonarrClient(SONARR_URL, SONARR_API_KEY)
    ok = client.ping()
    logger.info("Sonarr online: %s", ok)
    return ok


def get_sonarr_series_all_tvmaze_ids() -> List[int]:
    client = SonarrClient(SONARR_URL, SONARR_API_KEY)
    series = client.get_all_series()
    tvmaze_ids = []
    seen = set()
    for s in series:
        tvmz = s.get("tvMazeId") or s.get("tvmazeId") or s.get("tvMazeID") or s.get("tvmaze_id")
        if tvmz is None:
            continue
        try:
            it = int(tvmz)
        except Exception:
            continue
        if it not in seen:
            seen.add(it)
            tvmaze_ids.append(it)
    logger.debug("Sonarr tvmaze ids: %s", tvmaze_ids)
    return tvmaze_ids


def del_from_sonarr(series_id: int, delete_files: bool = False) -> bool:
    client = SonarrClient(SONARR_URL, SONARR_API_KEY)
    return client.delete_series(series_id, delete_files=delete_files)


def add_to_sonarr(tvdb_id: int, series_name: str) -> Optional[dict]:
    client = SonarrClient(SONARR_URL, SONARR_API_KEY)
    # determine root folder
    root_folder = SONARR_ROOTFOLDER
    if not root_folder:
        rf = client.get_sonarr_rootfolder()
        root_folder = rf.get("path") if rf else None
    if not root_folder:
        logger.warning("No Sonarr root folder available. Cannot add series %s (tvdb %s).", series_name, tvdb_id)
        return None

    return client.add_series(
        series_name=series_name,
        tvdb_id=tvdb_id,
        root_folder=root_folder,
        quality_profile_id=SONARR_QUALITYPROFILE,
        monitored=SONARR_MONITORED,
        search_for_missing=False,
    )

def sync_nousa_sonarr(delete_files: bool = False):
    logger.info("Starting sync_nousa_sonarr (allowed_list=%s)", NOUSA_ALLOWED_LIST)

    allowed_list = NOUSA_ALLOWED_LIST or []

    if not is_sonarr_online():
        logger.warning("Sonarr offline. Aborting sync.")
        return

    # Sonarr maps
    sonarr_tvmaze_map = _get_sonarr_map_tvmaze_to_sonarrid()
    sonarr_tvdb_map = _get_sonarr_map_tvdb_to_sonarrid()  # now returns {tvdb: {sonarr_id, series_name}}

    sonarr_tvmaze_ids = set(sonarr_tvmaze_map.keys())
    sonarr_tvdb_ids = set(sonarr_tvdb_map.keys())

    # Nousa data
    nousa_rows = get_nousa_series_all(allowed_list=allowed_list)
    nousa_tvdb_map = get_nousa_map_tvdb_to_name(nousa_rows)  # tvdb -> name
    nousa_tvdb_ids = set(nousa_tvdb_map.keys())
    nousa_tvmaze_ids = get_nousa_tvmaze_ids(nousa_rows)

    # --- DELETE ---
    to_delete_tvdb = sonarr_tvdb_ids - nousa_tvdb_ids
    logger.info("To delete from Sonarr (tvdb ids): %s", sorted(to_delete_tvdb))
    
    for tvdb in sorted(to_delete_tvdb):
        entry = sonarr_tvdb_map.get(tvdb)
        if not entry:
            logger.warning("No Sonarr entry found for tvdb %s; skipping", tvdb)
            continue

        sonarr_id = entry["sonarr_id"]
        series_name = entry.get("series_name", "Unknown")

        ok = del_from_sonarr(sonarr_id, delete_files=delete_files)
        if ok:
            logger.info("Deleted %s (tvdb %s, Sonarr id %s)", series_name, tvdb, sonarr_id)
        else:
            logger.warning("Failed to delete %s (tvdb %s, Sonarr id %s)", series_name, tvdb, sonarr_id)

        time.sleep(0.1)

    # --- ADD ---
    to_add_tvdb = nousa_tvdb_ids - sonarr_tvdb_ids
    logger.info("To add to Sonarr (tvdb ids): %s", sorted(to_add_tvdb))

    for tvdb in sorted(to_add_tvdb):
        series_name = nousa_tvdb_map.get(tvdb, f"tvdb-{tvdb}")
        res = add_to_sonarr(tvdb, series_name)
        if res:
            logger.info("Added %s (tvdb %s) to Sonarr", series_name, tvdb)
        else:
            logger.warning("Failed to add %s (tvdb %s) to Sonarr", series_name, tvdb)
        time.sleep(0.1)

    logger.info("Sync finished.")
