"""lists: add jellyfin_user_id

Links a nousa list to a Jellyfin user, so /recommendations can show
the series that this user can see in Jellyfin.

Revision ID: 7c2e9b41d5a3
Revises: f03e0ca24b22
Create Date: 2026-11-22 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c2e9b41d5a3'
down_revision: Union[str, None] = 'f03e0ca24b22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('Lists', sa.Column('jellyfin_user_id', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('Lists') as batch_op:
        batch_op.drop_column('jellyfin_user_id')
