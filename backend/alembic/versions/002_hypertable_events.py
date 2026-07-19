"""Make job_events a TimescaleDB hypertable + add co-occurrence continuous aggregate.

Revision ID: 002
Revises: 001
"""


from alembic import op

revision: str = "002"
down_revision: str = "001"
branch_labels: str | list[str] | None = None
depends_on: str | list[str] | None = None


def upgrade() -> None:
    # TimescaleDB needs the partitioning column in the primary key, and ALL
    # unique indexes must include it. Drop the fingerprint unique constraint
    # (dedupe is enforced in app code instead).
    op.execute("ALTER TABLE job_events DROP CONSTRAINT IF EXISTS job_events_fingerprint_key")

    # TimescaleDB needs the partitioning column in the primary key.
    op.execute("ALTER TABLE job_skills DROP CONSTRAINT IF EXISTS job_skills_event_id_fkey")
    op.execute("ALTER TABLE job_events DROP CONSTRAINT IF EXISTS job_events_pkey")
    op.execute("ALTER TABLE job_events ADD PRIMARY KEY (event_id, posted_at)")
    op.execute("ALTER TABLE job_skills ADD COLUMN IF NOT EXISTS posted_at TIMESTAMP WITH TIME ZONE")
    op.execute("UPDATE job_skills s SET posted_at = e.posted_at FROM job_events e WHERE s.event_id = e.event_id")
    op.execute("ALTER TABLE job_skills ALTER COLUMN posted_at SET NOT NULL")
    op.execute(
        "ALTER TABLE job_skills ADD FOREIGN KEY (event_id, posted_at) "
        "REFERENCES job_events (event_id, posted_at) ON DELETE CASCADE"
    )

    # job_events was a plain table; promote it to a hypertable on posted_at.
    # migrate_data => TRUE because the table may already hold rows. The FK is
    # dropped above so the internal data migration truncate can succeed.
    op.execute(
        "SELECT create_hypertable('job_events', 'posted_at', "
        "if_not_exists := TRUE, migrate_data => TRUE)"
    )

    # Continuous aggregate: rolling 30-day co-occurrence window. Created WITH NO
    # DATA; it is refreshed on first ingest (pipeline) and on a schedule, not
    # here — refreshing inside the migration txn deadlocks on table locks.
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS cooccurrence_30d
        WITH (timescaledb.continuous) AS
        SELECT
            a.skill AS skill_a,
            b.skill AS skill_b,
            time_bucket(INTERVAL '1 day', e.posted_at) AS bucket,
            COUNT(*) AS pair_count,
            MIN(e.posted_at) AS first_seen,
            MAX(e.posted_at) AS last_seen
        FROM job_skills a
        JOIN job_skills b ON a.event_id = b.event_id AND a.skill < b.skill
        JOIN job_events e ON e.event_id = a.event_id
        WHERE e.posted_at >= NOW() - INTERVAL '30 days'
        GROUP BY a.skill, b.skill, time_bucket(INTERVAL '1 day', e.posted_at)
        WITH NO DATA;
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS cooccurrence_30d")
    op.execute("SELECT drop_chunks('job_events', INTERVAL '0 days')")
    op.execute("ALTER TABLE job_events DROP CONSTRAINT job_events_pkey")
    op.execute("ALTER TABLE job_events ADD PRIMARY KEY (event_id)")
    op.execute(
        "ALTER TABLE job_skills ADD FOREIGN KEY (event_id) "
        "REFERENCES job_events (event_id) ON DELETE CASCADE"
    )
