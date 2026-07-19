"""Add provenance url column to job_events for data verification.

Revision ID: 003
Revises: 002
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: str = "002"
branch_labels: Union[str, list[str], None] = None
depends_on: Union[str, list[str], None] = None


def upgrade() -> None:
    # ponytail: nullable column on a hypertable is safe; historical rows simply
    # have null url. The existing `source` column is now populated with the real
    # origin (Remotive/Arbeitnow/Naukri) by the pipeline.
    op.add_column("job_events", sa.Column("url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("job_events", "url")
