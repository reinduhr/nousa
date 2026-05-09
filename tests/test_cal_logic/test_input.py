import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from starlette.requests import Request
from starlette.templating import _TemplateResponse
from datetime import datetime, timedelta

from src.cal_logic.input import add_series_to_list
from src.cal_logic.input import add_episodes
from src.models import Series, ListEntries, Lists, Episodes


@pytest.mark.asyncio
async def test_add_series_to_list_new_series(db_session):
    # 1. Setup Mock Data
    series_id = 123
    list_id = 1
    series_name = "Great Show"
    
    # Pre-populate the list in the DB so get_record finds it
    db_session.add(Lists(list_id=list_id, list_name="My Watchlist"))
    db_session.commit()

    # 2. Setup Mock Request
    form_data = MagicMock()
    form_data.get.side_effect = lambda key: {
        "series-id": str(series_id),
        "list-id": str(list_id),
        "series-name": series_name
    }.get(key)
    
    request = AsyncMock(spec=Request)
    request.form = AsyncMock(return_value=form_data)
    request.client.host = "127.0.0.1"

    # 3. Mock External API Responses (fetch_series_data)
    mock_sdata = {
        "name": series_name,
        "status": "Running",
        "externals": {"thetvdb": 456, "imdb": "tt123"}
    }
    mock_edata = [{"id": 1, "name": "Pilot", "season": 1, "number": 1, "airdate": "2024-01-01"}]

    # 4. Patch SessionLocal in all relevant places and mock the API
    with patch("src.cal_logic.input.SessionLocal") as mock_ops_session, \
         patch("src.helpers.logging.SessionLocal") as mock_log_session, \
         patch("src.cal_logic.input.fetch_data") as mock_fetch:
        
        # Point all sessions to our test db_session
        mock_ops_session.return_value.__enter__.return_value = db_session
        mock_log_session.return_value.__enter__.return_value = db_session
        
        # Mock the two API calls (series and episodes)
        mock_fetch.side_effect = [mock_sdata, mock_edata]

        # 5. Execute
        response = await add_series_to_list(request)

    # 6. Assertions
    assert isinstance(response, _TemplateResponse)
    assert response.context["message"] == f"{series_name} has been added"

    # Verify Series was created
    series_rec = db_session.query(Series).filter_by(series_id=series_id).first()
    assert series_rec is not None
    assert series_rec.series_name == series_name

    # Verify List Entry was created
    entry_rec = db_session.query(ListEntries).filter_by(series_id=series_id, list_id=list_id).first()
    assert entry_rec is not None


def test_add_episodes_filters_and_saves(db_session):
    # 1. Setup Data
    series_id = 999
    now = datetime.now()
    
    # We create three episodes: 
    # One valid (today), one too old (2 years ago), one too far future (2 years future)
    mock_edata = [
        {
            "id": 101,
            "name": "Valid Episode",
            "season": 1,
            "number": 1,
            "airdate": now.strftime("%Y-%m-%d")
        },
        {
            "id": 102,
            "name": "Too Old Episode",
            "season": 1,
            "number": 2,
            "airdate": (now - timedelta(days=730)).strftime("%Y-%m-%d")
        },
        {
            "id": 103,
            "name": "Too Far Future Episode",
            "season": 1,
            "number": 3,
            "airdate": (now + timedelta(days=730)).strftime("%Y-%m-%d")
        }
    ]

    # 2. Patch SessionLocal to use our test db_session
    with patch("src.cal_logic.input.SessionLocal") as mock_session_factory:
        mock_session_factory.return_value.__enter__.return_value = db_session
        
        # 3. Execute
        add_episodes(series_id, mock_edata)

    # 4. Assertions
    # Check that only the valid episode was saved to the DB
    saved_episodes = db_session.query(Episodes).filter_by(ep_series_id=series_id).all()
    
    assert len(saved_episodes) == 1
    assert saved_episodes[0].ep_id == 101
    assert saved_episodes[0].ep_name == "Valid Episode"
    
    # Verify the date conversion handled correctly
    assert isinstance(saved_episodes[0].ep_airdate, datetime)
    assert saved_episodes[0].ep_airdate.date() == now.date()