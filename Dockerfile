FROM python:3.12.3-slim
WORKDIR /code
RUN addgroup --gid 3333 nousa
RUN adduser --uid 3333 --gid 3333 --no-create-home nousa

# DEPENDENCIES
RUN apt-get update && apt-get install -y sqlite3

# PROGRAM FILES
COPY ./src ./src
COPY ./static ./static
COPY ./templates ./templates
COPY ./compose.yaml .
COPY ./Dockerfile .
COPY ./requirements.txt .
#--no-cache-dir (option for pip install)
RUN pip install -r requirements.txt
RUN chmod +x ./src/*.py

# ENVIRONMENT VARIABLES
ENV TZ='Europe/Amsterdam'
ENV PYTHONPATH /code/src
EXPOSE 5000

# ALEMBIC DB MIGRATIONS
COPY ./alembic ./alembic
#RUN chmod +x ./alembic/versions/*.py
COPY ./alembic.ini .

# USER (COMMENT USER OUT FOR PRODUCTION CONTAINER!)
RUN mkdir -m 770 data
RUN chown -R 3333:3333 data
#USER nousa

# LAUNCH!
# DEV
CMD uvicorn src.main:app --host 0.0.0.0 --port 5000 --reload && alembic upgrade head
# PROD
#CMD uvicorn src.main:app --host 0.0.0.0 --port 5000 && alembic upgrade head

# NOT IN USE
#RUN alembic upgrade head
#CMD ["alembic", "upgrade", "head"]
#CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5000", "--reload"]