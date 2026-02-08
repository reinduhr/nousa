import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.templating import Jinja2Templates


from src.cal_logic.list_ops import create_list, rename_list
from src.models import Lists, AuditLogEntry
from src.db import SessionLocal  # Assuming this is your session maker

@pytest.mark.asyncio
async def test_create_list_valid_input():
    # Mock form data and request
    form_data = AsyncMock()
    form_data.get.return_value = "validlist123"
    request = AsyncMock(spec=Request)
    request.form = AsyncMock(return_value=form_data)
    request.client.host = "127.0.0.1"

    # Mock DB session
    with patch('src.cal_logic.list_ops.SessionLocal') as mock_session_local:
        mock_session = mock_session_local.return_value.__enter__.return_value
        mock_session.execute.return_value.scalars.return_value.all.return_value = []  # Empty lists
        mock_session.execute.return_value.scalars.return_value.first.return_value = None  # No name conflict
        mock_new_list = Lists(list_name="validlist123")
        mock_new_list.list_id = 1
        mock_session.add.return_value = None
        mock_session.commit.return_value = None

        response = await create_list(request)

    assert isinstance(response, Jinja2Templates)
    assert response.template.name == 'lists.html'
    assert response.context['message'] == "validlist123 has been created"
    mock_session.add.assert_called()  # Called for list and audit log
    mock_session.commit.assert_called()

@pytest.mark.asyncio
async def test_create_list_invalid_characters():
    form_data = AsyncMock()
    form_data.get.return_value = "invalid@list"
    request = AsyncMock(spec=Request)
    request.form = AsyncMock(return_value=form_data)

    with patch('src.cal_logic.list_ops.SessionLocal') as mock_session_local:
        mock_session = mock_session_local.return_value.__enter__.return_value
        mock_session.execute.return_value.scalars.return_value.all.return_value = []  # Empty lists

        response = await create_list(request)

    assert isinstance(response, Jinja2Templates)
    assert response.context['message'] == "Only letters and numbers are accepted"

@pytest.mark.asyncio
async def test_create_list_name_conflict():
    form_data = AsyncMock()
    form_data.get.return_value = "existinglist"
    request = AsyncMock(spec=Request)
    request.form = AsyncMock(return_value=form_data)

    with patch('src.cal_logic.list_ops.SessionLocal') as mock_session_local:
        mock_session = mock_session_local.return_value.__enter__.return_value
        mock_session.execute.return_value.scalars.return_value.all.return_value = []  # Empty lists
        mock_session.execute.return_value.scalars.return_value.first.return_value = Lists(list_name="existinglist")  # Conflict

        response = await create_list(request)

    assert isinstance(response, Jinja2Templates)
    assert response.context['message'] == "A list with that name exists already"

@pytest.mark.asyncio
async def test_rename_list_valid():
    form_data = AsyncMock()
    form_data.get.side_effect = ["1", "newname123"]  # list-id, rename-list
    request = AsyncMock(spec=Request)
    request.form = AsyncMock(return_value=form_data)
    request.client.host = "127.0.0.1"

    with patch('src.cal_logic.list_ops.SessionLocal') as mock_session_local:
        mock_session = mock_session_local.return_value.__enter__.return_value
        mock_prev_list = Lists(list_name="oldname")
        mock_session.execute.return_value.scalar_one.return_value = mock_prev_list
        mock_session.execute.return_value.scalar_one.return_value = 0  # No name conflict
        mock_session.commit.return_value = None

        response = await rename_list(request)

    assert isinstance(response, RedirectResponse)
    assert response.headers['location'] == "/list/1"
    mock_session.add.assert_called_with(AuditLogEntry)  # Audit log added
    mock_session.commit.assert_called()

# Add more tests for invalid list_id, name conflicts, etc.