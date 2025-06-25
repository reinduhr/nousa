import os
import smtplib
from email.message import EmailMessage
import logging
from datetime import datetime
from sqlalchemy import select

from .db import SessionLocal
from .models import AuditLogEntry

class Mailer:
    def __init__(self, body=None):

        self.sender_email = os.getenv("SENDER_EMAIL", None)
        self.sender_password = os.getenv("SENDER_PASSWORD", None)

        self.receiver_email = os.getenv("RECEIVER_EMAIL", None)

        self.smtp_server = os.getenv("SMTP_SERVER", None)
        self.smtp_port = os.getenv("SMTP_PORT", None)

        self.subject = "📅 nousa 📺 tv calendar notification"
        self.body = body or self.create_weekly_notification_email()

    def send(self):
            if not self.body:
                return
            
            # Create message container
            msg = EmailMessage()
            msg['From'] = f"nousa <{self.sender_email}>"
            msg['To'] = self.receiver_email
            msg['Subject'] = self.subject
            msg.set_content(self.body)

            try:
                # Establish a connection with the SMTP server
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls() # Secure the connection using TLS
                    server.login(self.sender_email, self.sender_password)  # Login to the email server
                    # Send email
                    server.sendmail(self.sender_email, self.receiver_email, msg.as_string())
                    logging.info(f"Mail sent successfully; {self.subject}")
            except Exception as e:
                logging.error(f"An error occurred: {e}")
    
    def create_weekly_notification_email(self):
        with SessionLocal() as session:
            body = []

            log_entries = session.execute(select(AuditLogEntry)
                .where(AuditLogEntry.mail_sent == 0)
            ).scalars().all()

            for entry in log_entries:
                text = self.add_entry(entry)
                body.append(text)
                entry.mail_sent = 1

            session.commit()
            return ''.join(body)

    def add_entry(self, entry):

        # series_add
        if entry.msg_type_id == 1:
            text = (
                f"{entry.created_at.strftime("%A %-d %B %Y %H:%M:%S")} - {entry.msg_type_name} - {entry.ip}\n"
                f"Series {entry.series_name} has been added to List: {entry.list_id}.\n\n"
            )

        # series_archive
        elif entry.msg_type_id == 2:
            text = (
                f"{entry.created_at.strftime("%A %-d %B %Y %H:%M:%S")} - {entry.msg_type_name} - {entry.ip}\n"
                f"Series {entry.series_name} has been added to the Archive of List: {entry.list_id}.\n\n"
            )
            
        # series_delete
        elif entry.msg_type_id == 3:
            text = (
                f"{entry.created_at.strftime("%A %-d %B %Y %H:%M:%S")} - {entry.msg_type_name} - {entry.ip}\n"
                f"Series {entry.series_name} has been deleted from List: {entry.list_id}.\n\n"
            )

        # list_create
        elif entry.msg_type_id == 4:
            text = (
                f"{entry.created_at.strftime("%A %-d %B %Y %H:%M:%S")} - {entry.msg_type_name} - {entry.ip}\n"
                f"List {entry.list_id}: {entry.list_name} has been created.\n\n"
            )

        # list_rename
        elif entry.msg_type_id == 5:
            text = (
                f"{entry.created_at.strftime("%A %-d %B %Y %H:%M:%S")} - {entry.msg_type_name} - {entry.ip}\n"
                f"List {entry.list_id} {entry.prev_list_name} has been renamed to: {entry.list_name}.\n\n"
            )
        
        return text
    
def send_weekly_notification_email():
    mailer = Mailer()
    mailer.send()