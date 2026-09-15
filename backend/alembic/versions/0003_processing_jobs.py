"""Add durable video processing jobs."""

from alembic import op
import sqlalchemy as sa

revision = "0003_processing_jobs"
down_revision = "0002_video_upload_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "video_processing_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("video_id", sa.Uuid(), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("queue_message_id", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("video_id", "job_type", name="uq_video_processing_job_type"),
    )
    op.create_index("ix_video_processing_jobs_video_id", "video_processing_jobs", ["video_id"])


def downgrade() -> None:
    op.drop_index("ix_video_processing_jobs_video_id", table_name="video_processing_jobs")
    op.drop_table("video_processing_jobs")
