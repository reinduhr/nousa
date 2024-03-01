# models.py
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, BLOB, DateTime
from sqlalchemy.orm import declarative_base, relationship

engine = create_engine("sqlite:///src/myCal1.db")
Base = declarative_base()

class Series(Base):
    __tablename__ = "Series"

    series_id = Column(Integer, primary_key=True)
    series_name = Column(String)
    series_status = Column(String)

class Episodes(Base):
    __tablename__ = "Episodes"

    ep_series_id = Column(Integer)#, ForeignKey("Series.series_id"))
    ep_id = Column(Integer, primary_key=True)
    ep_name = Column(String)
    ep_season = Column(String)
    ep_number = Column(String)
    ep_airdate = Column(DateTime)

"""
def fetch_and_store_series(series_name, session):
    response = requests.get(f"https://api.tvmaze.com/search/shows?q={series_name}")
    data = response.json()
    series_list = []
    for entry in data:
        show = entry.get("show", {})
        series = Series(
            series_id=show.get("id"),
            series_url=show.get("url"),
            series_name=show.get("name")
        )
        series_list.append(series)
        episodes = Episodes(
            series_id=show.get"id
        )
    session.add_all(series_list)
    session.commit()
"""
Base.metadata.create_all(engine)
