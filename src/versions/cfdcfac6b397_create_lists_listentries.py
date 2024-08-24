"""create_lists_listentries

Revision ID: cfdcfac6b397
Revises: 3700df429d28
Create Date: 2024-08-19 13:35:51.555877

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cfdcfac6b397'
down_revision: Union[str, None] = '3700df429d28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Step 1: Create the Lists table
    op.create_table(
        'Lists',
        sa.Column('list_id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('list_name', sa.String, nullable=False),
    )
    
    # Step 2: Create the ListEntries table
    op.create_table(
        'ListEntries',
        sa.Column('list_id', sa.Integer, nullable=False, primary_key=True),
        sa.Column('series_id', sa.Integer, nullable=False, primary_key=True),
        sa.Column('archive', sa.Integer, nullable=False, default=0),
        sa.PrimaryKeyConstraint()
    )
    
    # Step 3: Create a default list with list_id=1 and list_name='firstlist'
    op.execute(
        "INSERT INTO Lists (list_id, list_name) VALUES (1, 'unnamed')"
    )

    # Step 4: Copy data from SeriesArchive to ListEntries with archive=1 (True) Plus make sure this entry is not in Series because we don't want duplicates
    op.execute(
        "INSERT INTO ListEntries (list_id, series_id, archive) SELECT 1, series_id, 1 FROM SeriesArchive WHERE series_id NOT IN (SELECT series_id FROM Series)"
    )
    
    # Step 5: Copy data from Series to ListEntries with archive=0 (False)
    op.execute(
        "INSERT INTO ListEntries (list_id, series_id, archive) SELECT 1, series_id, 0 FROM Series"
    )

	# Step 6: Copy unique series_id from SeriesArchive to Series
    op.execute(
		"""
		INSERT INTO Series (series_id)
		SELECT sear.series_id
		FROM SeriesArchive sear
		WHERE NOT EXISTS (
			SELECT 1 FROM Series se WHERE se.series_id = sear.series_id
		)
		"""
	)

    # Step 7: Delete table SeriesArchive
    op.drop_table('SeriesArchive')

def downgrade():
    op.drop_table('ListEntries')
    op.drop_table('Lists')
