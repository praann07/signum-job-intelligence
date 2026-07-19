import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Text,
)
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Employer(Base):
    __tablename__ = "employers"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    size: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        CheckConstraint(
            "size IN ('seed', 'early', 'mid', 'late', 'public', 'unknown')",
            name="ck_employer_size",
        ),
    )


class JobEvent(Base):
    __tablename__ = "job_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    posted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        primary_key=True,
        server_default=sa_text("NOW()"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employers.company_id"), nullable=False
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str] = mapped_column(
        Text, nullable=False, default="unknown"
    )
    seniority: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC)
    )
    fingerprint: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "seniority IN ('intern', 'junior', 'mid', 'senior', 'lead', 'unknown')",
            name="ck_job_seniority",
        ),
    )


class JobSkill(Base):
    __tablename__ = "job_skills"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    skill: Mapped[str] = mapped_column(Text, primary_key=True)
    posted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    is_known: Mapped[bool] = mapped_column(Boolean, default=True)
    extraction_confidence: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        ForeignKeyConstraint(
            ["event_id", "posted_at"],
            ["job_events.event_id", "job_events.posted_at"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "extraction_confidence >= 0 AND extraction_confidence <= 1",
            name="ck_confidence_range",
        ),
    )


class SkillTaxonomy(Base):
    __tablename__ = "skill_taxonomy"

    skill: Mapped[str] = mapped_column(Text, primary_key=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    added_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC)
    )
    added_by: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "category IN ('language', 'framework', 'tool', 'cloud', "
            "'database', 'concept', 'platform')",
            name="ck_skill_category",
        ),
        CheckConstraint(
            "added_by IN ('seed', 'discovered', 'manual')",
            name="ck_provenance",
        ),
    )


class SkillCooccurrence(Base):
    __tablename__ = "skill_cooccurrence"

    skill_a: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_b: Mapped[str] = mapped_column(Text, primary_key=True)
    window_start: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), primary_key=True
    )
    window_end: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    pair_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    last_seen: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    breakout_score: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        CheckConstraint("skill_a < skill_b", name="ck_pair_order"),
    )


class EmergingCandidate(Base):
    __tablename__ = "emerging_candidates"

    token: Mapped[str] = mapped_column(Text, primary_key=True)
    first_seen: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC)
    )
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    accepted: Mapped[bool | None] = mapped_column(Boolean)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)
