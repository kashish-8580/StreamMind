"""Add original video upload metadata."""

from alembic import op
import sqlalchemy as sa

revision = "0002_video_upload_fields"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("original_s3_key", sa.String(1024), nullable=True))
    op.add_column("videos", sa.Column("original_filename", sa.String(255), nullable=True))
    op.add_column("videos", sa.Column("content_type", sa.String(100), nullable=True))
    op.add_column("videos", sa.Column("expected_file_size", sa.BigInteger(), nullable=True))
    op.add_column("videos", sa.Column("uploaded_file_size", sa.BigInteger(), nullable=True))
    op.add_column("videos", sa.Column("upload_etag", sa.String(255), nullable=True))
    op.add_column("videos", sa.Column("upload_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint("uq_videos_original_s3_key", "videos", ["original_s3_key"])


def downgrade() -> None:
    op.drop_constraint("uq_videos_original_s3_key", "videos", type_="unique")
    for column in (
        "upload_completed_at",
        "upload_etag",
        "uploaded_file_size",
        "expected_file_size",
        "content_type",
        "original_filename",
        "original_s3_key",
    ):
        op.drop_column("videos", column)
