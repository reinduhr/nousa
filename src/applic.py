from sqlalchemy.orm import sessionmaker
from models import Series, engine
Session = sessionmaker(bind=engine)
session = Session()
show = Series(series_id=33, series_url="https://example.com", series_name="Example name")
session.add(show)
session.commit()