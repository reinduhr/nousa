import os
import aiohttp
import logging
from typing import Optional

NTFY_URL = os.getenv('NTFY_URL', None)

logger = logging.getLogger(__name__)
_session: Optional[aiohttp.ClientSession] = None

def get_ntfy_url(topic: str) -> Optional[str]:
    if not NTFY_URL:
        return None

    base = NTFY_URL.rstrip("/")
    return f"{base}/{topic}"

async def get_session() -> aiohttp.ClientSession:
    global _session

    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()

    return _session


async def send_ntfy(
    message: str,
    topic: str,
    title: str,
    priority: str,
):
    url = get_ntfy_url(topic)
    if not url:
        return  # silently skip if not configured

    headers = {
        "Priority": priority,
    }

    if title:
        headers["Title"] = title

    session = await get_session()

    async with session.post(
        url,
        data=message,
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=5),
        ssl=False
    ) as resp:
        resp.raise_for_status()
