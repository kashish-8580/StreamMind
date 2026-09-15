# StreamMind

StreamMind is an AI-powered video knowledge and streaming platform. The current local vertical slice provides authentication, an ownership-scoped video library, direct video uploads to private MinIO object storage, and asynchronous FFmpeg processing.

## Local development

1. Copy `.env.example` to `.env` and replace `JWT_SECRET`.
2. Run `docker compose up --build`.
3. Open the frontend at `http://localhost:5173` and the API docs at `http://localhost:8000/docs`.

MinIO's administration console is available at `http://localhost:9001`. The
development credentials are documented in `.env.example`; change them if the
services are exposed beyond your machine.

The backend runs database migrations before starting. Run tests with `docker compose run --rm backend pytest`.

ElasticMQ exposes a local SQS-compatible endpoint at `http://localhost:9324`.
It starts the `video-processing` queue and its dead-letter queue automatically.

## First API flow

1. `POST /auth/register`
2. `POST /auth/login` to receive a bearer token.
3. Use that token with `POST /videos` and `GET /videos`.

## Direct video uploads

The upload API uses an S3-compatible presigned POST so video bytes travel
directly from the browser to object storage instead of through FastAPI. Docker
Compose starts MinIO, creates a private bucket, and allows the local frontend origin
automatically:

1. `POST /videos/upload-url` with the title, filename, content type, and exact
   file size.
2. Submit the returned form fields and file to the returned MinIO URL.
3. `POST /videos/{id}/complete-upload`; the API verifies the object in storage
   and saves a durable processing job before publishing it to the queue.

The upload states are `PENDING_UPLOAD → UPLOADED → QUEUED`. If queue
publication fails, the upload and pending database job remain safe so a repeated
completion request can retry. Duplicate completion requests do not create a
second job after successful publication.

## Local video processing

The `video-worker` service consumes the durable processing queue, downloads the
original from MinIO, validates it with FFprobe, creates a 720p HLS rendition and
JPEG thumbnail with FFmpeg, and uploads the assets to the private processed-video
bucket. A successful job advances through `QUEUED → PROCESSING → STREAM_READY`.
The video record then contains its duration, HLS manifest key, and thumbnail key.

Failed processing attempts are recorded as `PROCESSING_FAILED`, including a
diagnostic message on the job. The queue message is left for retry and eventually
moves to the configured dead-letter queue after repeated failures. The worker
starts only after migrations and the API health check complete.

## Secure local playback

For a `STREAM_READY` video, `GET /videos/{id}/playback` verifies ownership and
returns the HLS manifest with short-lived signed URLs for every media segment,
plus a signed thumbnail URL. The private processed-video bucket therefore stays
closed to anonymous access. These URLs expire after 15 minutes by default.

The frontend refreshes queued/processing states automatically and shows a Play
button when a video becomes ready. It uses native HLS where available and loads
HLS.js on demand in other modern browsers.

## Local transcription and search

After video processing, a separate durable `transcription` queue hands the
original video to the CPU-only transcription worker. It extracts mono 16 kHz
audio with FFmpeg, transcribes it locally with Faster Whisper, and stores
timestamped segments in PostgreSQL. The video remains playable while this
independent AI stage runs.

- `GET /videos/{id}/transcript` returns ordered timestamped segments and status.
- `GET /videos/{id}/transcript/search?q=...` searches up to 100 matching segments.
- The player displays transcript progress, text, timestamps, and search results.

The default `tiny` multilingual model keeps local CPU and memory usage low. Its
first use downloads the open-source model into the persistent `whisper-models`
Docker volume. Set `WHISPER_MODEL=base` or `small` for better accuracy at the
cost of a larger download and slower CPU processing. No AWS or paid AI API is
needed for this workflow.

Accepted formats are MP4, QuickTime/MOV, and WebM. The default size limit is
2 GiB and presigned forms expire after 15 minutes. The bucket must remain private;
the presigned form grants narrowly scoped, temporary upload access. For AWS
later, remove the custom S3 endpoint settings and replace the local credentials
and bucket name; the application-level upload flow remains the same.

## Project layout

- `frontend/`: React + TypeScript UI
- `backend/`: FastAPI API, database models, migrations, and tests
- `elasticmq/`: local SQS-compatible queue and DLQ configuration
- `infra/`: planned AWS CDK application
- `workers/`: asynchronous FFmpeg video processing worker and tests

The detailed project plan is currently maintained in the workspace-level `../plan.md` and should be committed into this repository before the first push.
