"""create SeriesArchive column for status

Revision ID: 451153d8a380
Revises: 
Create Date: 2024-04-06 19:38:04.896047

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '451153d8a380'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('SeriesArchive', sa.Column('series_status', sa.String(length=50), nullable=True))


def downgrade() -> None:
    pass
