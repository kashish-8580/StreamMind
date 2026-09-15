import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import TranscriptSegment, User, Video, VideoProcessingJob
from app.queue import ProcessingQueue, QueueUnavailableError, get_processing_queue
from app.config import settings
from app.schemas import (
    LoginRequest,
    PlaybackResponse,
    RegisterRequest,
    TokenResponse,
    TranscriptResponse,
    UploadUrlRequest,
    UploadUrlResponse,
    ProcessingJobResponse,
    VideoCreate,
    VideoResponse,
    VideoStatusResponse,
)
from app.security import create_access_token, hash_password, verify_password
from app.storage import ObjectNotFoundError, S3Storage, get_storage

ALLOWED_VIDEO_TYPES = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
}

app = FastAPI(title="StreamMind API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id))


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return TokenResponse(access_token=create_access_token(user.id))


@app.post("/videos", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
def create_video(payload: VideoCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Video:
    video = Video(user_id=current_user.id, title=payload.title.strip(), description=payload.description)
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


@app.post("/videos/upload-url", response_model=UploadUrlResponse, status_code=status.HTTP_201_CREATED)
def create_upload_url(
    payload: UploadUrlRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: S3Storage = Depends(get_storage),
) -> UploadUrlResponse:
    if payload.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported video content type")
    if payload.file_size > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Video exceeds upload size limit")

    filename = Path(payload.filename).name
    if not filename or filename in {".", ".."}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid filename")

    video_id = uuid.uuid4()
    object_key = f"users/{current_user.id}/videos/{video_id}/source{ALLOWED_VIDEO_TYPES[payload.content_type]}"
    video = Video(
        id=video_id,
        user_id=current_user.id,
        title=payload.title.strip(),
        description=payload.description,
        status="PENDING_UPLOAD",
        original_s3_key=object_key,
        original_filename=filename,
        content_type=payload.content_type,
        expected_file_size=payload.file_size,
    )
    db.add(video)
    db.flush()
    upload = storage.create_upload(object_key, payload.content_type, payload.file_size)
    db.commit()
    db.refresh(video)
    return UploadUrlResponse(
        video=VideoResponse.model_validate(video),
        upload={"url": upload["url"], "fields": upload["fields"]},
        expires_in=settings.presigned_upload_expire_seconds,
    )


@app.post("/videos/{video_id}/complete-upload", response_model=VideoResponse)
def complete_upload(
    video_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: S3Storage = Depends(get_storage),
    queue: ProcessingQueue = Depends(get_processing_queue),
) -> Video:
    video = db.get(Video, video_id)
    if video is None or video.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    if video.status == "QUEUED":
        return video
    if video.status not in {"PENDING_UPLOAD", "UPLOADED"} or video.original_s3_key is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Video is not awaiting an upload")

    if video.status == "PENDING_UPLOAD":
        try:
            uploaded = storage.inspect_object(video.original_s3_key)
        except ObjectNotFoundError:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Uploaded object was not found")

        actual_size = int(uploaded["ContentLength"])
        actual_type = uploaded.get("ContentType")
        if actual_size != video.expected_file_size or actual_type != video.content_type:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Uploaded object does not match its declaration",
            )

        video.status = "UPLOADED"
        video.uploaded_file_size = actual_size
        video.upload_etag = str(uploaded.get("ETag", "")).strip('"') or None
        video.upload_completed_at = datetime.now(timezone.utc)

    job = db.scalar(
        select(VideoProcessingJob).where(
            VideoProcessingJob.video_id == video.id,
            VideoProcessingJob.job_type == "VIDEO_PROCESSING",
        )
    )
    if job is None:
        job = VideoProcessingJob(video_id=video.id, job_type="VIDEO_PROCESSING", status="PENDING")
        db.add(job)
    db.commit()
    db.refresh(job)

    if job.status != "QUEUED":
        try:
            message_id = queue.enqueue(
                {
                    "job_id": str(job.id),
                    "video_id": str(video.id),
                    "user_id": str(current_user.id),
                    "bucket": settings.s3_upload_bucket,
                    "object_key": video.original_s3_key,
                    "job_type": "VIDEO_PROCESSING",
                }
            )
        except QueueUnavailableError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Upload is saved; processing will be queued when the queue is available",
            )
        job.status = "QUEUED"
        job.queue_message_id = message_id
        video.status = "QUEUED"
        db.commit()
        db.refresh(video)
    return video


@app.get("/videos", response_model=list[VideoResponse])
def list_videos(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Video]:
    return list(db.scalars(select(Video).where(Video.user_id == current_user.id).order_by(Video.created_at.desc())))


@app.get("/videos/{video_id}", response_model=VideoResponse)
def get_video(video_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Video:
    video = db.get(Video, video_id)
    if video is None or video.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return video


@app.get("/videos/{video_id}/status", response_model=VideoStatusResponse)
def get_video_status(
    video_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VideoStatusResponse:
    video = db.get(Video, video_id)
    if video is None or video.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    job = db.scalar(
        select(VideoProcessingJob)
        .where(VideoProcessingJob.video_id == video.id)
        .order_by(VideoProcessingJob.created_at.desc())
    )
    return VideoStatusResponse(
        video_id=video.id,
        video_status=video.status,
        processing_job=ProcessingJobResponse.model_validate(job) if job else None,
    )


@app.get("/videos/{video_id}/playback", response_model=PlaybackResponse)
def get_video_playback(
    video_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: S3Storage = Depends(get_storage),
) -> PlaybackResponse:
    video = db.get(Video, video_id)
    if video is None or video.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    if video.status != "STREAM_READY" or not video.hls_manifest_key or not video.thumbnail_key:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Video is not ready for playback")

    manifest_key = PurePosixPath(video.hls_manifest_key)
    manifest = storage.read_processed_text(video.hls_manifest_key)
    rewritten_lines: list[str] = []
    for line in manifest.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            rewritten_lines.append(line)
            continue
        relative_asset = PurePosixPath(stripped)
        if relative_asset.is_absolute() or ".." in relative_asset.parts:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid stream manifest")
        asset_key = str(manifest_key.parent / relative_asset)
        rewritten_lines.append(storage.create_processed_download_url(asset_key))

    return PlaybackResponse(
        manifest="\n".join(rewritten_lines) + "\n",
        thumbnail_url=storage.create_processed_download_url(video.thumbnail_key),
        expires_in=settings.presigned_upload_expire_seconds,
    )


def _owned_video(video_id: uuid.UUID, user_id: uuid.UUID, db: Session) -> Video:
    video = db.get(Video, video_id)
    if video is None or video.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return video


@app.get("/videos/{video_id}/transcript", response_model=TranscriptResponse)
def get_video_transcript(
    video_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranscriptResponse:
    video = _owned_video(video_id, current_user.id, db)
    segments = list(
        db.scalars(
            select(TranscriptSegment)
            .where(TranscriptSegment.video_id == video.id)
            .order_by(TranscriptSegment.start_seconds)
        )
    )
    return TranscriptResponse(video_id=video.id, status=video.transcript_status, segments=segments)


@app.get("/videos/{video_id}/transcript/search", response_model=TranscriptResponse)
def search_video_transcript(
    video_id: uuid.UUID,
    q: str = Query(min_length=1, max_length=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranscriptResponse:
    video = _owned_video(video_id, current_user.id, db)
    escaped_query = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    if not escaped_query:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Search query cannot be blank")
    segments = list(
        db.scalars(
            select(TranscriptSegment)
            .where(
                TranscriptSegment.video_id == video.id,
                TranscriptSegment.text.ilike(f"%{escaped_query}%", escape="\\"),
            )
            .order_by(TranscriptSegment.start_seconds)
            .limit(100)
        )
    )
    return TranscriptResponse(video_id=video.id, status=video.transcript_status, segments=segments)
