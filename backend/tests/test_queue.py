import json

from app.config import settings
from app.queue import ProcessingQueue


class SqsClient:
    def __init__(self):
        self.request = None

    def send_message(self, **kwargs):
        self.request = kwargs
        return {"MessageId": "message-123"}

    def receive_message(self, **kwargs):
        self.request = kwargs
        return {"Messages": [{"MessageId": "message-123", "ReceiptHandle": "receipt"}]}

    def delete_message(self, **kwargs):
        self.request = kwargs


def test_processing_message_is_serialized_for_sqs():
    storage = ProcessingQueue.__new__(ProcessingQueue)
    storage.client = SqsClient()
    storage.queue_url = settings.video_processing_queue_url
    message = {"job_id": "job-1", "video_id": "video-1"}

    message_id = storage.enqueue(message)

    assert message_id == "message-123"
    assert storage.client.request["QueueUrl"] == settings.video_processing_queue_url
    assert json.loads(storage.client.request["MessageBody"]) == message


def test_processing_message_can_be_received_and_deleted():
    queue = ProcessingQueue.__new__(ProcessingQueue)
    queue.client = SqsClient()
    queue.queue_url = settings.video_processing_queue_url

    messages = queue.receive()
    queue.delete(messages[0]["ReceiptHandle"])

    assert messages[0]["MessageId"] == "message-123"
    assert queue.client.request["ReceiptHandle"] == "receipt"
