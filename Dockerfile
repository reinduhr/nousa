FROM python:3.12.3-slim
WORKDIR /code

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

# ALEMBIC
COPY ./alembic ./alembic
#RUN chmod +x ./alembic/versions/*.py
COPY ./alembic.ini .

# LAUNCH!
CMD uvicorn src.main:app --host 0.0.0.0 --port 5000 --reload && alembic upgrade head
#RUN alembic upgrade head
#CMD ["alembic", "upgrade", "head"]
#CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5000", "--reload"]