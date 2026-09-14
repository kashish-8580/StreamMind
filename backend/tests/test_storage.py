from app.config import settings
from app.storage import S3Storage


class PresignClient:
    def generate_presigned_post(self, **kwargs):
        return {
            "url": "http://minio:9000/streammind-original-videos",
            "fields": {"key": kwargs["Key"]},
        }


def test_presigned_upload_uses_browser_visible_minio_url(monkeypatch):
    monkeypatch.setattr(settings, "s3_endpoint_url", "http://minio:9000")
    monkeypatch.setattr(settings, "s3_public_endpoint_url", "http://localhost:9000")
    storage = S3Storage.__new__(S3Storage)
    storage.client = PresignClient()

    upload = storage.create_upload("users/1/videos/2/source.mp4", "video/mp4", 100)

    assert upload["url"] == "http://localhost:9000/streammind-original-videos"
