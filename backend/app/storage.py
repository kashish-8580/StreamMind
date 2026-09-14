from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import settings


class ObjectNotFoundError(Exception):
    pass


class S3Storage:
    def __init__(self) -> None:
        kwargs: dict[str, Any] = {
            "region_name": settings.aws_region,
            "config": Config(s3={"addressing_style": "path" if settings.s3_force_path_style else "auto"}),
        }
        if settings.s3_endpoint_url:
            kwargs["endpoint_url"] = settings.s3_endpoint_url
        self.client = boto3.client("s3", **kwargs)

    def create_upload(self, object_key: str, content_type: str, file_size: int) -> dict[str, Any]:
        upload = self.client.generate_presigned_post(
            Bucket=settings.s3_upload_bucket,
            Key=object_key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", file_size, file_size],
            ],
            ExpiresIn=settings.presigned_upload_expire_seconds,
        )
        if settings.s3_endpoint_url and settings.s3_public_endpoint_url:
            upload["url"] = upload["url"].replace(
                settings.s3_endpoint_url.rstrip("/"),
                settings.s3_public_endpoint_url.rstrip("/"),
                1,
            )
        return upload

    def inspect_object(self, object_key: str) -> dict[str, Any]:
        try:
            return self.client.head_object(Bucket=settings.s3_upload_bucket, Key=object_key)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise ObjectNotFoundError(object_key) from exc
            raise


def get_storage() -> S3Storage:
    return S3Storage()
