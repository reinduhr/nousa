"""add_jellyfin_tables

Revision ID: a14719ead282
Revises: 838442e7f881
Create Date: 2025-06-15 16:11:28.936024

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a14719ead282'
down_revision: Union[str, None] = '838442e7f881'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'JellyfinRecommendation',
        sa.Column('series_id', sa.String(), primary_key=True),
        sa.Column('series_ext_imdb', sa.String()),
        sa.Column('series_ext_thetvdb', sa.String()),
        sa.Column('series_name', sa.String()),
        sa.Column('year_start', sa.Integer()),
        sa.Column('year_end', sa.Integer()),
        sa.Column('status', sa.String()),
        sa.Column('description', sa.String()),
        sa.Column('url_img_medium', sa.String()),
    )

    """ op.create_table(
        'JellyfinUsername',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('jellyfin_userid', sa.String(), unique=True),
        sa.Column('jellyfin_username', sa.String(), unique=True),
    ) """



def downgrade() -> None:
    op.drop_table('JellyfinUsername')
    op.drop_table('JellyfinRecommendation')
