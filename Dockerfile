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
COPY ./alembic.ini .
RUN pip install -r requirements.txt --no-cache-dir
RUN chmod +x ./src/*.py
RUN chmod +x ./src/versions/*.py

# ENVIRONMENT VARIABLES
ENV TZ='Europe/Amsterdam'
ENV PYTHONPATH /code/src
EXPOSE 5000

# USER (COMMENT USER OUT FOR DEV CONTAINER!)
RUN mkdir -m 770 data
RUN chown -R 3333:3333 data
USER nousa

# LAUNCH!
# DEV
#CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5000", "--reload"]

# PROD
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5000"]

# NOT IN USE
#CMD alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 5000 --reload
#RUN alembic upgrade head
#CMD ["alembic", "upgrade", "head"]
#CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5000", "--reload"]