
from datetime import datetime
from sqlalchemy import update, delete
from sqlalchemy.orm import Session
import logging

from src.db import SessionLocal
from src.models import Series, Episodes

logger = logging.getLogger(__name__)

def series_update(series_id, db: Session = None):
    # imports go here to prevent circular import error
    from src.cal_logic.gather import try_request_series, try_request_episodes
    from src.cal_logic.input import add_episodes
    sdata = try_request_series(series_id)
    edata = try_request_episodes(series_id)
    if sdata is not None:
        today = datetime.now()
        sdata_name = sdata['name']
        sdata_status = sdata['status']
        sdata_ext_thetvdb = sdata['externals'].get('thetvdb')
        sdata_ext_imdb = sdata['externals'].get('imdb')

        if db is None:
            context = SessionLocal()
        else: # create a dummy context manager in order to still use 'with'
            from contextlib import nullcontext
            context = nullcontext(db)

        with context as session:
            session.execute(
                update(Series)
                .where(Series.series_id == series_id)
                .values(
                    series_name=sdata_name,
                    series_status=sdata_status,
                    series_ext_thetvdb=sdata_ext_thetvdb,
                    series_ext_imdb=sdata_ext_imdb,
                    series_last_updated=today,
                )
            )

            # Episodes
            if edata is not None:
                # Delete old episode data
                session.execute(delete(Episodes).where(Episodes.ep_series_id == series_id))
                session.commit()
                # Add new episode data
                add_episodes(series_id, edata)
            session.commit()
            logger.info(f"series_update success. series_id: {series_id}")
            return True
    return False
