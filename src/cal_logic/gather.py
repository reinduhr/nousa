import aiohttp
import requests
import logging
import time

#from src.scheduler import schedule_series_update_retry, schedule_episodes_update_retry

logger = logging.getLogger(__name__)

# asynchronous api calls used in add_to_database()
async def fetch_data(url):
    async with aiohttp.ClientSession() as aiosession:
	    async with aiosession.get(url) as aioresponse:
                return await aioresponse.json()

# scheduler runs a weekly cronjob; 'series_update'
# the function 'series_update' runs 'try_request_series'
# the function 'try_request_series' runs 'request_series', and retries if it fails
# After a successful run all TV show data has been refreshed
def request_series(series_id):
    try:
        response_series = requests.get(f"https://api.tvmaze.com/shows/{series_id}", timeout=10)
        response_series.raise_for_status()
        return response_series.json()
    except:
        return None

def try_request_series(series_id, max_retries=30, delay=60): # try a request every minute for half an hour, if all fail then schedule new job in 24h
    retries = 0
    while retries < max_retries:
        result = request_series(series_id)
        if result is not None:
            return result
        retries += 1
        logger.error(f'series_update series retry {retries}')
        time.sleep(delay)
    
    #schedule_series_update_retry(series_id, max_retries)
    raise Exception


def request_episodes(series_id):
    try:
        response_episodes = requests.get(f"https://api.tvmaze.com/shows/{series_id}/episodes", timeout=10)
        response_episodes.raise_for_status()
        return response_episodes.json()
    except:
        return None

def try_request_episodes(series_id, max_retries=30, delay=60): # try a request every minute for half an hour, if all fail then schedule new job in 24h
    retries = 0
    while retries < max_retries:
        result = request_episodes(series_id)
        if result is not None:
            return result
        retries += 1
        logger.error(f'series_update episodes retry {retries}')
        time.sleep(delay)

    #schedule_episodes_update_retry(series_id, max_retries)
    raise Exception
