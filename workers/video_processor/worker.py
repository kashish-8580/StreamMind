import json
import logging
import mimetypes
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import Video, VideoProcessingJob
from app.queue import ProcessingQueue, QueueUnavailableError
from app.storage import S3Storage
from video_processor.ffmpeg_service import FFmpegService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def process_message(
    message: dict,
    queue: ProcessingQueue,
    transcription_queue: ProcessingQueue,
    storage: S3Storage,
    ffmpeg: FFmpegService,
) -> None:
    payload = json.loads(message["Body"])
    job_id = uuid.UUID(payload["job_id"])
    video_id = uuid.UUID(payload["video_id"])

    with SessionLocal() as db:
        job = db.get(VideoProcessingJob, job_id)
        video = db.get(Video, video_id)
        if job is None or video is None:
            logger.error("Discarding message for missing job or video: %s", job_id)
            queue.delete(message["ReceiptHandle"])
            return
        if job.status == "COMPLETED":
            queue.delete(message["ReceiptHandle"])
            return

        job.status = "PROCESSING"
        job.attempt_count += 1
        job.started_at = datetime.now(timezone.utc)
        job.error_message = None
        video.status = "PROCESSING"
        db.commit()

        try:
            with tempfile.TemporaryDirectory(prefix="streammind-") as temporary:
                workspace = Path(temporary)
                source = workspace / (video.original_filename or "source.mp4")
                storage.download_original(payload["object_key"], source)
                metadata = ffmpeg.inspect(source)
                hls_dir = workspace / "hls"
                manifest = ffmpeg.create_hls(source, hls_dir)
                thumbnail = workspace / "thumbnail.jpg"
                ffmpeg.create_thumbnail(source, thumbnail, metadata["duration_seconds"])

                prefix = f"users/{payload['user_id']}/videos/{video.id}"
                for asset in hls_dir.iterdir():
                    content_type = {
                        ".m3u8": "application/vnd.apple.mpegurl",
                        ".ts": "video/mp2t",
                    }.get(asset.suffix, mimetypes.guess_type(asset.name)[0] or "application/octet-stream")
                    storage.upload_processed(asset, f"{prefix}/hls/{asset.name}", content_type)
                thumbnail_key = f"{prefix}/thumbnail.jpg"
                storage.upload_processed(thumbnail, thumbnail_key, "image/jpeg")

                video.hls_manifest_key = f"{prefix}/hls/{manifest.name}"
                video.thumbnail_key = thumbnail_key
                video.duration_seconds = metadata["duration_seconds"]
                video.status = "STREAM_READY"
                transcription_job = db.scalar(
                    select(VideoProcessingJob).where(
                        VideoProcessingJob.video_id == video.id,
                        VideoProcessingJob.job_type == "TRANSCRIPTION",
                    )
                )
                if transcription_job is None:
                    transcription_job = VideoProcessingJob(
                        video_id=video.id,
                        job_type="TRANSCRIPTION",
                        status="PENDING",
                    )
                    db.add(transcription_job)
                    db.flush()
                if transcription_job.status not in {"QUEUED", "PROCESSING", "COMPLETED"}:
                    transcription_job.queue_message_id = transcription_queue.enqueue(
                        {
                            "job_id": str(transcription_job.id),
                            "video_id": str(video.id),
                            "object_key": payload["object_key"],
                            "job_type": "TRANSCRIPTION",
                        }
                    )
                    transcription_job.status = "QUEUED"
                    video.transcript_status = "QUEUED"
                job.status = "COMPLETED"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
            queue.delete(message["ReceiptHandle"])
            logger.info("Completed video processing job %s", job_id)
        except Exception as exc:
            db.rollback()
            job = db.get(VideoProcessingJob, job_id)
            video = db.get(Video, video_id)
            job.status = "FAILED"
            job.error_message = str(exc)[:4000]
            video.status = "PROCESSING_FAILED"
            db.commit()
            logger.exception("Video processing job %s failed", job_id)


def run() -> None:
    queue = ProcessingQueue()
    transcription_queue = ProcessingQueue(settings.transcription_queue_url)
    storage = S3Storage()
    ffmpeg = FFmpegService(settings.max_video_duration_seconds)
    logger.info("Video processor started")
    while True:
        try:
            for message in queue.receive():
                process_message(message, queue, transcription_queue, storage, ffmpeg)
        except QueueUnavailableError:
            logger.exception("Processing queue unavailable")
            time.sleep(5)
        except Exception:
            logger.exception("Unexpected message processing failure")
            time.sleep(1)


if __name__ == "__main__":
    run()
