import os
import smtplib
from email.message import EmailMessage
import logging
from datetime import datetime

class Mailer:
    def __init__(self, subject, body):

        self.sender_email = os.getenv("SENDER_EMAIL", None)
        self.sender_password = os.getenv("SENDER_PASSWORD", None)

        self.receiver_email = os.getenv("RECEIVER_EMAIL", None)

        self.smtp_server = os.getenv("SMTP_SERVER", None)
        self.smtp_port = os.getenv("SMTP_PORT", None)

        self.subject = subject
        self.body = body

    def send(self):
        
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
                logging.error(f"An error occurred: {e} while trying to send mail with subject: {self.subject}")
 
def create_mail(mtype, series_name=None, list_id=None, request=None, list_name=None, prev_list_name=None):
    now = datetime.now()

    if mtype == "add":
        subject = f"📅 nousa 📺 | {series_name} has been added to list {list_id}"
        body = f"nousa self-hosted tv calendar\n\nSeries: {series_name}\nList ID: {list_id}\nTime: {now:%c}\nIP: {request.client.host}\n"
    
    if mtype == "archive":
        subject = f"📅 nousa 📺 | {series_name} has been archived on list {list_id}"
        body = f"nousa self-hosted tv calendar\n\nSeries: {series_name}\nList ID: {list_id}\nTime: {now:%c}\nIP: {request.client.host}\n"
    
    if mtype == "delete":
        subject = f"📅 nousa 📺 | {series_name} has been deleted from list {list_id}"
        body = f"nousa self-hosted tv calendar\n\nSeries: {series_name}\nList ID: {list_id}\nTime: {now:%c}\nIP: {request.client.host}\n"
    
    if mtype == "create":
        subject = f"📅 nousa 📺 | List {list_id} has been created with the name: {list_name}"
        body = f"nousa self-hosted tv calendar\n\nList name: {list_name}\nList ID: {list_id}\nTime: {now:%c}\nIP: {request.client.host}\n"

    if mtype == "rename":
        subject = f"📅 nousa 📺 | List {list_id} has been renamed from {prev_list_name} to {list_name}"
        body = f"nousa self-hosted tv calendar\n\nPrevious list name: {prev_list_name}\nNew list name: {list_name}\nList ID: {list_id}\nTime: {now:%c}\nIP: {request.client.host}\n"

    mail = Mailer(
        subject = subject,
        body = body
    )

    if mail.sender_email and mail.sender_password and mail.receiver_email and mail.smtp_server and mail.smtp_port:
        return mail
    
    else:
        logging.info("No mail was sent due to Mailer lacking login credentials")