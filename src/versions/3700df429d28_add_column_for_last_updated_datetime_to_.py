"""add column for last_updated datetime to series and series_archive

Revision ID: 3700df429d28
Revises: 
Create Date: 2024-06-10 15:16:32.018700

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3700df429d28'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('Series', sa.Column('series_last_updated', sa.DateTime, nullable=True))
    op.add_column('SeriesArchive', sa.Column('series_last_updated', sa.DateTime, nullable=True))


def downgrade() -> None:
    op.drop_column('Series', 'series_last_updated')
    op.drop_column('SeriesArchive', 'series_last_updated')

