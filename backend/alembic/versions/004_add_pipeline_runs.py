"""Add pipeline_runs table for per-source ingest run history.

Revision ID: 004
Revises: 003
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "004"
down_revision: str = "003"
branch_labels: str | list[str] | None = None
depends_on: str | list[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pipeline_runs",
        sa.Column(
            "run_id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("fetched", sa.Integer(), server_default=sa.text("0")),
        sa.Column("inserted", sa.Integer(), server_default=sa.text("0")),
        sa.Column("skipped", sa.Integer(), server_default=sa.text("0")),
        sa.Column("error", sa.Text()),
        sa.Column("duration_ms", sa.Integer()),
    )


def downgrade() -> None:
    op.drop_table("pipeline_runs")
