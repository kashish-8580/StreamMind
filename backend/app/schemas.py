import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(RegisterRequest):
    pass


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class VideoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)


class VideoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    status: str
    original_filename: str | None
    content_type: str | None
    expected_file_size: int | None
    uploaded_file_size: int | None
    upload_completed_at: datetime | None
    hls_manifest_key: str | None
    thumbnail_key: str | None
    duration_seconds: float | None
    transcript_status: str
    created_at: datetime
    updated_at: datetime


class UploadUrlRequest(VideoCreate):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str
    file_size: int = Field(gt=0)


class PresignedPost(BaseModel):
    url: str
    fields: dict[str, str]


class UploadUrlResponse(BaseModel):
    video: VideoResponse
    upload: PresignedPost
    expires_in: int


class ProcessingJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_type: str
    status: str
    attempt_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class VideoStatusResponse(BaseModel):
    video_id: uuid.UUID
    video_status: str
    processing_job: ProcessingJobResponse | None


class PlaybackResponse(BaseModel):
    manifest: str
    thumbnail_url: str
    expires_in: int


class TranscriptSegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    start_seconds: float
    end_seconds: float
    text: str
    language: str | None


class TranscriptResponse(BaseModel):
    video_id: uuid.UUID
    status: str
    segments: list[TranscriptSegmentResponse]
