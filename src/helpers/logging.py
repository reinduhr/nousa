from datetime import datetime

from src.db import SessionLocal
from src.models import AuditLogEntry

async def add_audit_log_entry(
        msg_type_id: int,
        msg_type_name: str,
        ip: str,
        list_id: int = None,
        list_name: str = None,
        prev_list_name: str = None,
        series_id: int = None,
        series_name: str = None,
        created_at: datetime = datetime.now()
    ):
    
    audit_log_entry = AuditLogEntry(
            msg_type_id = msg_type_id,
            msg_type_name = msg_type_name,
            ip = ip,
            list_id = list_id,
            list_name = list_name,
            prev_list_name = prev_list_name,
            series_id = series_id,
            series_name = series_name,
        )
        
    with SessionLocal() as session:
        session.add(audit_log_entry)
        session.commit()