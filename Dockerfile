FROM python:3.12.0-slim

#RUN groupadd -r mycal && useradd -s /bin/bash -m -r -g mycal mycal

WORKDIR /code

RUN apt-get update && apt-get install -y cron
COPY ./nousa-crontab /etc/cron.d/nousa-crontab
RUN chmod 0644 /etc/cron.d/nousa-crontab && crontab /etc/cron.d/nousa-crontab

RUN apt install -y sqlite3

COPY ./requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./src ./src
RUN chmod +x ./src/*.py

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "80", "--reload"]

RUN /etc/init.d/cron start

ENV PYTHONPATH /code/src

#RUN chsh -s /usr/sbin/nologin root

#ENV HOME /home/mycal
#RUN chmod -R 777 /home/mycal