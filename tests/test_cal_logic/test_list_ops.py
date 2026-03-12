import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.templating import Jinja2Templates, _TemplateResponse

from src.cal_logic.list_ops import create_list, rename_list
from src.models import Lists, AuditLogEntry

@pytest.mark.asyncio
async def test_create_list_valid_input(db_session):
    # 1. Setup Mock Request (Keep this, as Request is hard to build manually)
    form_data = MagicMock()
    form_data.get.return_value = "validlist123"
    request = AsyncMock(spec=Request)
    request.form = AsyncMock(return_value=form_data)
    request.client.host = "127.0.0.1"

    # 2. Patch the SessionLocal factory in your app to use your TEST session
    # This ensures 'with SessionLocal()' inside your app uses the in-memory DB
    with patch('src.cal_logic.list_ops.SessionLocal') as mock_factory:
        # This makes the context manager return your real test session
        mock_factory.return_value.__enter__.return_value = db_session
        
        # 3. Call the function (it now runs against the real SQLite memory DB)
        response = await create_list(request)

    # 4. Assertions (Check the response AND the database)
    assert isinstance(response, _TemplateResponse)
    assert response.context['message'] == "validlist123 has been created"
    
    # Verify the data was actually saved to the in-memory DB
    saved_list = db_session.query(Lists).filter_by(list_name="validlist123").first()
    assert saved_list is not None

"""
@pytest.mark.asyncio
async def test_create_list_invalid_characters(db_session):
    form_data = AsyncMock()
    form_data.get.return_value = "invalid@list"
    request = AsyncMock(spec=Request)
    request.form = AsyncMock(return_value=form_data)

    db_session_local = db_session.return_value.__enter__.return_value
    db_session_local.execute.return_value.scalars.return_value.all.return_value = []  # Empty lists

    response = await create_list(request)

    assert isinstance(response, Jinja2Templates)
    assert response.context['message'] == "Only letters and numbers are accepted"

@pytest.mark.asyncio
async def test_create_list_name_conflict(db_session):
    form_data = AsyncMock()
    form_data.get.return_value = "existinglist"
    request = AsyncMock(spec=Request)
    request.form = AsyncMock(return_value=form_data)

    with patch(db_session) as mock_session_local:
        db_session_local = db_session.return_value.__enter__.return_value
        db_session_local.execute.return_value.scalars.return_value.all.return_value = []  # Empty lists
        db_session_local.execute.return_value.scalars.return_value.first.return_value = Lists(list_name="existinglist")  # Conflict

        response = await create_list(request)

    assert isinstance(response, Jinja2Templates)
    assert response.context['message'] == "A list with that name exists already"
"""
@pytest.mark.asyncio
async def test_rename_list_valid(db_session):
    # 1. Setup Data in the real in-memory DB
    original_list = Lists(list_name="oldname")
    new_list_name = "newname123"
    db_session.add(original_list)
    db_session.commit()
    db_session.refresh(original_list)
    list_id = original_list.list_id

    # 2. Setup Mock Request
    form_data = MagicMock()
    # Mocking the two form inputs: 'list-id' and 'new-name' (or whatever your keys are)
    form_data.get.side_effect = [str(list_id), new_list_name] 
    request = AsyncMock(spec=Request)
    request.form = AsyncMock(return_value=form_data)
    request.client.host = "127.0.0.1"

    # 3. Patch SessionLocal to use our real test DB session
    with patch('src.cal_logic.list_ops.SessionLocal') as mock_factory:
        mock_factory.return_value.__enter__.return_value = db_session

        response = await rename_list(request)

    # 4. Assertions
    assert isinstance(response, RedirectResponse)
    assert response.headers['location'] == f"/list/{list_id}"

    # Verify the database was actually updated
    db_session.expire_all() # Ensure we aren't looking at cached data
    updated_list = db_session.get(Lists, list_id)
    assert updated_list.list_name == new_list_name

    # Verify Audit Log was created
    audit = db_session.query(AuditLogEntry).filter(
        AuditLogEntry.list_id == list_id,
        AuditLogEntry.list_name == new_list_name
    ).first()    
    assert audit is not None

