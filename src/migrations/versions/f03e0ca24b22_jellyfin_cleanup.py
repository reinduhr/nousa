"""jellyfin cleanup

Revision ID: f03e0ca24b22
Revises: a14719ead282
Create Date: 2025-08-17 08:45:39.116069

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f03e0ca24b22'
down_revision: Union[str, None] = 'a14719ead282'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('JellyfinRecommendation')


def downgrade() -> None:
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
