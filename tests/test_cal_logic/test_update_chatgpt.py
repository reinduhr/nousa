from datetime import datetime
from unittest.mock import patch

from src.cal_logic.update import series_update
from src.models import Series, Episodes

def test_series_update_updates_series_and_episodes(db_session):
    series_id = 123

    # --- Arrange -------------------------------------------------

    # Insert initial series row (required for UPDATE)
    db_session.add(
        Series(
            series_id=series_id,
            series_name="Old name",
            series_status="Ended",
            series_ext_thetvdb=None,
            series_ext_imdb=None,
        )
    )
    db_session.commit()

    mock_series_data = {
        "name": "New Series Name",
        "status": "Running",
        "externals": {
            "thetvdb": 456,
            "imdb": "tt1234567",
        },
    }

    mock_episode_data = [
        {
            "season": 1,
            "episode": 1,
            "title": "Pilot",
        }
    ]

    # --- Act -----------------------------------------------------

    with patch(
        "src.cal_logic.gather.try_request_series",
        return_value=mock_series_data,
    ), patch(
        "src.cal_logic.gather.try_request_episodes",
        return_value=mock_episode_data,
    ), patch(
        "src.cal_logic.input.add_episodes",
    ) as mock_add_episodes:

        series_update(series_id, db=db_session)

    # --- Assert --------------------------------------------------

    series = (
        db_session.query(Series)
        .filter(Series.series_id == series_id)
        .one()
    )

    assert series.series_name == "New Series Name"
    assert series.series_status == "Running"
    assert series.series_ext_thetvdb == 456
    assert series.series_ext_imdb == "tt1234567"
    assert isinstance(series.series_last_updated, datetime)

    # Episodes behavior
    mock_add_episodes.assert_called_once_with(series_id, mock_episode_data)
