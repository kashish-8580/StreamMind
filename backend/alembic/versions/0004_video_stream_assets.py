"""Add processed video asset metadata."""

from alembic import op
import sqlalchemy as sa

revision = "0004_video_stream_assets"
down_revision = "0003_processing_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("hls_manifest_key", sa.String(1024), nullable=True))
    op.add_column("videos", sa.Column("thumbnail_key", sa.String(1024), nullable=True))
    op.add_column("videos", sa.Column("duration_seconds", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "duration_seconds")
    op.drop_column("videos", "thumbnail_key")
    op.drop_column("videos", "hls_manifest_key")
