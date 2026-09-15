import json

from app.config import settings
from app.queue import ProcessingQueue


class SqsClient:
    def __init__(self):
        self.request = None

    def send_message(self, **kwargs):
        self.request = kwargs
        return {"MessageId": "message-123"}


def test_processing_message_is_serialized_for_sqs():
    storage = ProcessingQueue.__new__(ProcessingQueue)
    storage.client = SqsClient()
    message = {"job_id": "job-1", "video_id": "video-1"}

    message_id = storage.enqueue(message)

    assert message_id == "message-123"
    assert storage.client.request["QueueUrl"] == settings.video_processing_queue_url
    assert json.loads(storage.client.request["MessageBody"]) == message
