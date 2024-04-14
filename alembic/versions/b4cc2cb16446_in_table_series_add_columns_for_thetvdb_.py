"""in table Series add columns for thetvdb and imdb

Revision ID: b4cc2cb16446
Revises: 451153d8a380
Create Date: 2024-04-14 15:28:06.556431

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4cc2cb16446'
down_revision: Union[str, None] = '451153d8a380'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
	op.add_column('Series', sa.Column('series_ext_thetvdb', sa.Integer, nullable=True))
	op.add_column('Series', sa.Column('series_ext_imdb', sa.String, nullable=True))


def downgrade() -> None:
    pass
