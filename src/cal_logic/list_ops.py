from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqlalchemy import select, update, func
import re
from datetime import datetime

from src.services.templates import templates
from src.db import SessionLocal
from src.models import Lists, AuditLogEntry

async def create_list(request: Request):
    with SessionLocal() as session:
        lists = session.execute(select(Lists)).scalars().all()
        form_data = await request.form()
        user_input = form_data.get('create-list')
        name_check = session.execute(select(Lists).where(Lists.list_name == user_input)).scalars().first()
        # validate to only accept letters and numbers
        pattern = r'^[a-zA-Z0-9]+$'
        if not re.match(pattern, user_input):
            message = "Only letters and numbers are accepted"
            return templates.TemplateResponse('lists.html', {'request': request, 'message': message, 'lists': lists})
        else:
            if not name_check:
                new_list = Lists(list_name=user_input)
                session.add(new_list)
                session.commit()
                lists = session.execute(select(Lists)).scalars().all()
                
                message = f"{user_input} has been created"
                list_id = new_list.list_id

                audit_log_entry = AuditLogEntry(
                    msg_type_id = 4,
                    msg_type_name = "list_create",
                    ip = request.client.host,
                    list_id = list_id,
                    list_name = user_input,
                    prev_list_name = None,
                    series_id = None,
                    series_name = None,
                    created_at = datetime.now()
                )
                session.add(audit_log_entry)
                session.commit()
                
                return templates.TemplateResponse('lists.html', {'request': request, 'message': message, 'lists': lists})
            else:
                message = "A list with that name exists already"
                return templates.TemplateResponse('lists.html', {'request': request, 'message': message, 'lists': lists})

async def rename_list(request: Request):
    form_data = await request.form()
    list_id_form = form_data.get('list-id')
    user_input = form_data.get("rename-list")
    with SessionLocal() as session:
        prev = session.execute(select(Lists).where(Lists.list_id == list_id_form)).scalar_one()
        prev_list_name = prev.list_name
        try: # validate input
            list_id = int(list_id_form)
        except:
            message = "Error: Invalid input. Try again, but no tricks this time ;)"
            return templates.TemplateResponse('index.html', {'request': request, 'message': message})
        # validate to only accept letters and numbers
        pattern = r'^[a-zA-Z0-9]+$'
        if not re.match(pattern, user_input):
            message = "Only letters and numbers are accepted"
            return templates.TemplateResponse('index.html', {'request': request, 'message': message})
        name_check = session.execute(select(func.count()).where(Lists.list_name == user_input)).scalar_one()

        if name_check > 0:
            message = "A list with that name exists already"
            return templates.TemplateResponse('index.html', {'request': request, 'message': message})
        else:
            session.execute(update(Lists)
                .where(Lists.list_id == int(list_id))
                .values(list_name=user_input)
                .execution_options(synchronize_session='fetch')
            )
            session.commit()

            audit_log_entry = AuditLogEntry(
                msg_type_id = 5,
                msg_type_name = "list_rename",
                ip = request.client.host,
                list_id = list_id,
                list_name = user_input,
                prev_list_name = prev_list_name,
                series_id = None,
                series_name = None,
                created_at = datetime.now()
            )
            session.add(audit_log_entry)
            session.commit()
            
        return RedirectResponse(url=f"/list/{list_id}")
