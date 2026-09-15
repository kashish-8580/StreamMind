import json
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings


class QueueUnavailableError(Exception):
    pass


class ProcessingQueue:
    def __init__(self) -> None:
        kwargs: dict[str, Any] = {"region_name": settings.aws_region}
        if settings.sqs_endpoint_url:
            kwargs["endpoint_url"] = settings.sqs_endpoint_url
        self.client = boto3.client("sqs", **kwargs)

    def enqueue(self, message: dict[str, str]) -> str:
        try:
            response = self.client.send_message(
                QueueUrl=settings.video_processing_queue_url,
                MessageBody=json.dumps(message),
            )
        except (BotoCoreError, ClientError) as exc:
            raise QueueUnavailableError from exc
        return response["MessageId"]

    def receive(self) -> list[dict[str, str]]:
        try:
            response = self.client.receive_message(
                QueueUrl=settings.video_processing_queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,
                AttributeNames=["ApproximateReceiveCount"],
            )
        except (BotoCoreError, ClientError) as exc:
            raise QueueUnavailableError from exc
        return response.get("Messages", [])

    def delete(self, receipt_handle: str) -> None:
        try:
            self.client.delete_message(
                QueueUrl=settings.video_processing_queue_url,
                ReceiptHandle=receipt_handle,
            )
        except (BotoCoreError, ClientError) as exc:
            raise QueueUnavailableError from exc


def get_processing_queue() -> ProcessingQueue:
    return ProcessingQueue()
