"""create table AuditLogEntry

Revision ID: 838442e7f881
Revises: cfdcfac6b397
Create Date: 2025-05-31 11:47:47.636821

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '838442e7f881'
down_revision: Union[str, None] = 'cfdcfac6b397'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'AuditLogEntry',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('msg_type_id', sa.Integer),
        sa.Column('msg_type_name', sa.String),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('ip', sa.String),
        sa.Column('list_id', sa.Integer, nullable=True),
        sa.Column('list_name', sa.String, nullable=True),
        sa.Column('prev_list_name', sa.String, nullable=True),
        sa.Column('series_id', sa.Integer, nullable=True),
        sa.Column('series_name', sa.String, nullable=True),
        sa.Column('mail_sent', sa.Integer, nullable=False, server_default=sa.text('0')),
    )

def downgrade() -> None:
    op.drop_table('AuditLogEntry')
