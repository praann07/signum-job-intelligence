"""Initial schema with all tables

Revision ID: 001
Revises:
Create Date: 2026-07-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy import TIMESTAMP

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, list[str], None] = None
depends_on: Union[str, list[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    op.create_table(
        "employers",
        sa.Column("company_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.Text(), unique=True, nullable=False),
        sa.Column("size", sa.Text()),
        sa.Column("industry", sa.Text()),
        sa.Column("url", sa.Text()),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.CheckConstraint("size IN ('seed', 'early', 'mid', 'late', 'public', 'unknown')", name="ck_employer_size"),
    )

    op.create_table(
        "job_events",
        sa.Column("event_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("employers.company_id"), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("location", sa.Text()),
        sa.Column("country", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("seniority", sa.Text()),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("posted_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ingested_at", TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("fingerprint", sa.Text(), unique=True, nullable=False),
        sa.CheckConstraint("seniority IN ('intern', 'junior', 'mid', 'senior', 'lead', 'unknown')", name="ck_job_seniority"),
    )

    op.create_index("idx_jobs_posted_at", "job_events", [sa.text("posted_at DESC")])
    op.create_index("idx_jobs_country_seniority", "job_events", ["country", "seniority", sa.text("posted_at DESC")])

    op.create_table(
        "job_skills",
        sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("job_events.event_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("skill", sa.Text(), primary_key=True),
        sa.Column("is_known", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.Column("extraction_confidence", sa.Float()),
        sa.CheckConstraint("extraction_confidence >= 0 AND extraction_confidence <= 1", name="ck_confidence_range"),
    )
    op.create_index("idx_skills_skill", "job_skills", ["skill"])

    op.create_table(
        "skill_taxonomy",
        sa.Column("skill", sa.Text(), primary_key=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("aliases", ARRAY(sa.Text())),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.Column("added_at", TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("added_by", sa.Text(), nullable=False),
        sa.CheckConstraint("category IN ('language', 'framework', 'tool', 'cloud', 'database', 'concept', 'platform')", name="ck_skill_category"),
        sa.CheckConstraint("added_by IN ('seed', 'discovered', 'manual')", name="ck_provenance"),
    )

    op.create_table(
        "skill_cooccurrence",
        sa.Column("skill_a", sa.Text(), primary_key=True),
        sa.Column("skill_b", sa.Text(), primary_key=True),
        sa.Column("window_start", TIMESTAMP(timezone=True), primary_key=True),
        sa.Column("window_end", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("pair_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("first_seen", TIMESTAMP(timezone=True)),
        sa.Column("last_seen", TIMESTAMP(timezone=True)),
        sa.Column("breakout_score", sa.Float()),
        sa.CheckConstraint("skill_a < skill_b", name="ck_pair_order"),
    )
    op.execute("SELECT create_hypertable('skill_cooccurrence', 'window_start')")
    op.create_index("idx_cooc_breakout", "skill_cooccurrence", [sa.text("breakout_score DESC"), sa.text("window_start DESC")])

    op.create_table(
        "emerging_candidates",
        sa.Column("token", sa.Text(), primary_key=True),
        sa.Column("first_seen", TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("occurrence_count", sa.Integer(), server_default=sa.text("1")),
        sa.Column("reviewed", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("accepted", sa.Boolean()),
        sa.Column("reviewed_at", TIMESTAMP(timezone=True)),
        sa.Column("rejection_reason", sa.Text()),
    )
    op.create_index("idx_emerging_unreviewed", "emerging_candidates", [sa.text("first_seen DESC")], postgresql_where=sa.text("reviewed = FALSE"))


def downgrade() -> None:
    op.drop_table("emerging_candidates")
    op.drop_table("skill_cooccurrence")
    op.drop_table("skill_taxonomy")
    op.drop_table("job_skills")
    op.drop_table("job_events")
    op.drop_table("employers")
