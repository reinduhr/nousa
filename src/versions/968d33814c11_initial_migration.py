"""initial migration

Revision ID: 968d33814c11
Revises: 838442e7f881
Create Date: 2025-06-07 12:27:54.444396

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '968d33814c11'
down_revision: Union[str, None] = None #'838442e7f881'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.create_table(
        'Series',
        sa.Column('series_id', sa.Integer, primary_key=True),
        sa.Column('series_name', sa.String),
        sa.Column('series_status', sa.String)
    )

    op.create_table(
        'Episodes',
        sa.Column('ep_series_id', sa.Integer),
        sa.Column('ep_id', sa.Integer, primary_key=True),
        sa.Column('ep_name', sa.String),
        sa.Column('ep_season', sa.String),
        sa.Column('ep_number', sa.String),
        sa.Column('ep_airdate', sa.DateTime)
    )

    op.create_table(
        'SeriesArchive',
        sa.Column('series_id', sa.Integer, primary_key=True),
        sa.Column('series_name', sa.String)
    )


def downgrade() -> None:
    
    op.drop_table('Series')
    op.drop_table('Episodes')
    op.drop_table('SeriesArchive')
