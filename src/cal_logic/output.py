from starlette.requests import Request
from starlette.responses import StreamingResponse
from sqlalchemy import select
from datetime import datetime, timedelta
import logging
import io

from src.models import ListEntries, Series, Episodes
from src.db import SessionLocal

logger = logging.getLogger(__name__)

# download calendar
def download_calendar(request: Request):
    list_id = request.path_params['list_id']
    calendar_file_memory = io.BytesIO()
    calendar_file_memory.write(b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:nousa\nCALSCALE:GREGORIAN\n")

    with SessionLocal() as session:
        shows = session.execute(select(Series)
            .join(ListEntries, Series.series_id == ListEntries.series_id)
            .where(ListEntries.list_id == list_id)
        ).scalars().all()

        episodes = session.execute(select(Episodes)
            .join(ListEntries, Episodes.ep_series_id == ListEntries.series_id)
            .where(
                ListEntries.list_id == list_id,
                ListEntries.archive == 0
            )
        ).scalars().all()

        for show in shows:
            for episode in episodes:
                if episode.ep_series_id == show.series_id:
                    now = datetime.now()
                    ep_start = episode.ep_airdate + timedelta(days=1) # add one day for proper calendar event start date
                    ep_end = episode.ep_airdate + timedelta(days=2) # add two days for event end
                    start_convert = datetime.strftime(ep_start,'%Y%m%d') # convert datetime object to string
                    end_convert = datetime.strftime(ep_end,'%Y%m%d') # convert datetime object to string
                    
                    calendar_event = (
                        "BEGIN:VEVENT\n"
                        f"DTSTAMP:{now:%Y%m%d}T{now:%H%M%S}Z\n"
                        f"DTSTART;VALUE=DATE:{start_convert}\n"
                        f"DTEND;VALUE=DATE:{end_convert}\n"
                        f"DESCRIPTION:Episode name: {episode.ep_name}\\nLast updated: {show.series_last_updated:%d-%b-%Y %H:%M}\\nIMDb ID: {show.series_ext_imdb}\n"
                        f"SUMMARY:{show.series_name} S{int(episode.ep_season):02d}E{int(episode.ep_number):02d}\n"
                        f"UID:{episode.ep_id}\n"
                        "BEGIN:VALARM\n"
                        f"UID:{episode.ep_id}A\n"
                        "ACTION:DISPLAY\n"
                        f"TRIGGER;VALUE=DATE-TIME:{start_convert}T170000Z\n"
                        f"DESCRIPTION:{show.series_name} is on tv today!\n"
                        "END:VALARM\n"
                        "END:VEVENT\n"
                    )
                    
                    calendar_file_memory.write(calendar_event.encode('utf-8'))
        calendar_file_memory.write(b"END:VCALENDAR")
        calendar_file_memory.seek(0)
        logger.info(f"Calendar from {list_id} was downloaded from IP: {request.client.host}")
        headers = {'Content-Disposition': 'attachment; filename="nousa.ics"'}
        return StreamingResponse(calendar_file_memory, media_type="text/calendar", headers=headers)