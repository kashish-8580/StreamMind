import json
import logging
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete

from app.config import settings
from app.database import SessionLocal
from app.models import TranscriptSegment, Video, VideoProcessingJob
from app.queue import ProcessingQueue, QueueUnavailableError
from app.storage import S3Storage
from transcription.audio_service import AudioService
from transcription.whisper_service import WhisperService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def process_message(
    message: dict,
    queue: ProcessingQueue,
    storage: S3Storage,
    audio_service: AudioService,
    whisper: WhisperService,
) -> None:
    payload = json.loads(message["Body"])
    job_id = uuid.UUID(payload["job_id"])
    video_id = uuid.UUID(payload["video_id"])

    with SessionLocal() as db:
        job = db.get(VideoProcessingJob, job_id)
        video = db.get(Video, video_id)
        if job is None or video is None or job.job_type != "TRANSCRIPTION":
            logger.error("Discarding invalid transcription job %s", job_id)
            queue.delete(message["ReceiptHandle"])
            return
        if job.status == "COMPLETED":
            queue.delete(message["ReceiptHandle"])
            return

        job.status = "PROCESSING"
        job.attempt_count += 1
        job.started_at = datetime.now(timezone.utc)
        job.error_message = None
        video.transcript_status = "PROCESSING"
        db.commit()

        try:
            with tempfile.TemporaryDirectory(prefix="streammind-transcript-") as temporary:
                workspace = Path(temporary)
                source = workspace / (video.original_filename or "source.mp4")
                audio = workspace / "audio.wav"
                storage.download_original(payload["object_key"], source)
                audio_service.extract(source, audio)
                language, segments = whisper.transcribe(audio)

                db.execute(delete(TranscriptSegment).where(TranscriptSegment.video_id == video.id))
                db.add_all(
                    TranscriptSegment(video_id=video.id, language=language, **segment)
                    for segment in segments
                )
                video.transcript_status = "COMPLETED"
                job.status = "COMPLETED"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
            queue.delete(message["ReceiptHandle"])
            logger.info("Completed transcription job %s with %d segments", job_id, len(segments))
        except Exception as exc:
            db.rollback()
            job = db.get(VideoProcessingJob, job_id)
            video = db.get(Video, video_id)
            job.status = "FAILED"
            job.error_message = str(exc)[:4000]
            video.transcript_status = "FAILED"
            db.commit()
            logger.exception("Transcription job %s failed", job_id)


def run() -> None:
    queue = ProcessingQueue(settings.transcription_queue_url)
    storage = S3Storage()
    audio_service = AudioService()
    logger.info("Loading local Whisper model %s", settings.whisper_model)
    whisper = WhisperService(settings.whisper_model)
    logger.info("Transcription worker started")
    while True:
        try:
            for message in queue.receive():
                process_message(message, queue, storage, audio_service, whisper)
        except QueueUnavailableError:
            logger.exception("Transcription queue unavailable")
            time.sleep(5)
        except Exception:
            logger.exception("Unexpected transcription failure")
            time.sleep(1)


if __name__ == "__main__":
    run()
