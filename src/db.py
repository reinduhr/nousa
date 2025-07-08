from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging
import subprocess

engine = create_engine("sqlite:///data/nousa.db")
SessionLocal = sessionmaker(bind=engine)

logger = logging.getLogger(__name__)

# Alembic database migrations
async def db_migrations():
    result = subprocess.run(["alembic", "upgrade", "head"], capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Alembic database migrations failed: {result.stderr}")