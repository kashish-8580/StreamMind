"""Add timestamped video transcripts."""

from alembic import op
import sqlalchemy as sa

revision = "0005_transcripts"
down_revision = "0004_video_stream_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "videos",
        sa.Column("transcript_status", sa.String(32), nullable=False, server_default="NOT_STARTED"),
    )
    op.create_table(
        "transcript_segments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("start_seconds", sa.Float(), nullable=False),
        sa.Column("end_seconds", sa.Float(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transcript_segments_video_id", "transcript_segments", ["video_id"])
    op.create_index(
        "ix_transcript_segments_video_start",
        "transcript_segments",
        ["video_id", "start_seconds"],
    )


def downgrade() -> None:
    op.drop_index("ix_transcript_segments_video_start", table_name="transcript_segments")
    op.drop_index("ix_transcript_segments_video_id", table_name="transcript_segments")
    op.drop_table("transcript_segments")
    op.drop_column("videos", "transcript_status")
