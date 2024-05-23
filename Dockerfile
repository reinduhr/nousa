FROM python:3.12.3-slim
WORKDIR /code

RUN apt-get update && apt-get install -y sqlite3

COPY ./src ./src
COPY ./static ./static
COPY ./templates ./templates
COPY ./compose.yaml .
COPY ./Dockerfile .
COPY ./requirements.txt .
#--no-cache-dir (option for pip install)
RUN pip install -r requirements.txt
RUN chmod +x ./src/*.py

ENV TZ='Europe/Amsterdam'
ENV PYTHONPATH /code/src
EXPOSE 5000

COPY ./alembic ./alembic
RUN chmod +x ./alembic/versions/*.py
COPY ./alembic.ini .

#RUN alembic upgrade head
#CMD ["alembic", "upgrade", "head"]
#CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5000", "--reload"]
CMD uvicorn src.main:app --host 0.0.0.0 --port 5000 --reload && alembic upgrade head