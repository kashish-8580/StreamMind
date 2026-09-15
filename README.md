# StreamMind

StreamMind is an AI-powered video knowledge and streaming platform. The current local vertical slice provides authentication, an ownership-scoped video library, and direct video uploads to private MinIO object storage.

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

The resulting states are `PENDING_UPLOAD → UPLOADED → QUEUED`. If queue
publication fails, the upload and pending database job remain safe so a repeated
completion request can retry. Duplicate completion requests do not create a
second job after successful publication.

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
- `workers/`: planned asynchronous video and AI processing workers

The detailed project plan is currently maintained in the workspace-level `../plan.md` and should be committed into this repository before the first push.
