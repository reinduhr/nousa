FROM python:3.12.3-slim
WORKDIR /code

RUN apt-get update && apt-get install -y sqlite3

COPY ./alembic ./alembic
RUN chmod +x ./alembic/versions/*.py
COPY ./alembic.ini .
COPY ./src ./src
COPY ./static ./static
COPY ./templates ./templates
COPY ./compose.yaml .
COPY ./Dockerfile .
COPY ./README.md .
COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN chmod +x ./src/*.py

ENV PYTHONPATH /code/src
EXPOSE 5000

#RUN alembic upgrade head
#CMD ["alembic", "upgrade", "head"]
#CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5000", "--reload"]
CMD alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 5000 --reload