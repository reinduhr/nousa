from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, BLOB, DateTime
from sqlalchemy.orm import declarative_base, relationship

engine = create_engine("sqlite:///data/nousa.db")
Base = declarative_base()

class Series(Base):
    __tablename__ = "Series"

    series_id = Column(Integer, primary_key=True)
    series_name = Column(String)
    series_status = Column(String)
    series_ext_thetvdb = Column(Integer)
    series_ext_imdb = Column(String)
    series_last_updated = Column(DateTime)

class Episodes(Base):
    __tablename__ = "Episodes"

    ep_series_id = Column(Integer)
    ep_id = Column(Integer, primary_key=True)
    ep_name = Column(String)
    ep_season = Column(String)
    ep_number = Column(String)
    ep_airdate = Column(DateTime)

class SeriesArchive(Base):
    __tablename__ = "SeriesArchive"

    series_id = Column(Integer, primary_key=True)
    series_name = Column(String)
    series_status = Column(String)
    series_last_updated = Column(DateTime)

Base.metadata.create_all(engine)