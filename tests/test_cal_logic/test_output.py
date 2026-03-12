import pytest
from unittest.mock import AsyncMock, patch
import io
from starlette.responses import StreamingResponse
from starlette.requests import Request
from src.cal_logic.output import download_calendar
from src.models import Series, Episodes, ListEntries, Lists
from datetime import datetime, date


@pytest.mark.asyncio
async def test_download_calendar_success(db_session):
    # 1. Setup Database state
    # Create the list
    new_list = Lists(list_name="My Calendar")
    db_session.add(new_list)
    db_session.commit()
    list_id = new_list.list_id

    # Create a series
    show = Series(
        series_id=101, 
        series_name="The Test Show", 
        series_ext_imdb="tt12345",
        series_last_updated=datetime.now()
    )
    db_session.add(show)

    # Create an episode airing today
    today = date.today()
    episode = Episodes(
        ep_id=999,
        ep_series_id=101,
        ep_name="Pilot",
        ep_season=1,
        ep_number=1,
        ep_airdate=today
    )
    db_session.add(episode)

    # Link them in ListEntries
    entry = ListEntries(list_id=list_id, series_id=101, archive=0)
    db_session.add(entry)
    db_session.commit()

    # 2. Setup Mock Request with path_params
    request = AsyncMock(spec=Request)
    request.path_params = {'list_id': list_id}
    request.client.host = "127.0.0.1"

    # 3. Patch SessionLocal and Run
    with patch('src.cal_logic.output.SessionLocal') as mock_factory:
        mock_factory.return_value.__enter__.return_value = db_session
        
        response = download_calendar(request)

    # 4. Assertions
    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/calendar"
    assert "attachment; filename=\"nousa.ics\"" in response.headers['Content-Disposition']

    # Read the stream content
    # StreamingResponse body is an async iterator or a generator
    content = b""
    async for chunk in response.body_iterator:
        content += chunk
    
    ical_text = content.decode('utf-8')

    # Verify iCal structure
    assert "BEGIN:VCALENDAR" in ical_text
    assert "SUMMARY:The Test Show S01E01" in ical_text
    assert "UID:999" in ical_text
    assert "END:VCALENDAR" in ical_text