from sqlalchemy import create_engine, Column, Integer, String, DateTime, func
from sqlalchemy.orm import declarative_base

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

class Lists(Base):
    __tablename__ = "Lists"

    list_id = Column(Integer, primary_key=True, autoincrement=True)
    list_name = Column(String, unique=True, nullable=False)

class ListEntries(Base):
    __tablename__ = "ListEntries"

    list_id = Column(Integer, primary_key=True)
    series_id = Column(Integer, primary_key=True)
    archive = Column(Integer, default=0)

class AuditLogEntry(Base):
    __tablename__ = "AuditLogEntry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    msg_type_id = Column(Integer)
    msg_type_name = Column(String)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    ip = Column(String)
    list_id = Column(Integer, nullable=True)
    list_name = Column(String, nullable=True)
    prev_list_name = Column(String, nullable=True)
    series_id = Column(Integer, nullable=True)
    series_name = Column(String, nullable=True)
    mail_sent = Column(Integer, nullable=False, default=0)

class JellyfinRecommendation(Base):
    __tablename__ = "JellyfinRecommendation"

    series_id = Column(String, primary_key=True)
    series_ext_imdb = Column(String)
    series_ext_thetvdb = Column(String)
    series_name = Column(String)
    year_start = Column(Integer)
    year_end = Column(Integer)
    status = Column(String)
    description = Column(String)
    url_img_medium = Column(String)

""" class JellyfinUsername(Base):
    __tablename__ = "JellyfinUsername"

    id = Column(Integer, primary_key=True, autoincrement=True)
    jellyfin_userid = Column(String, unique=True)
    jellyfin_username = Column(String, unique=True) """