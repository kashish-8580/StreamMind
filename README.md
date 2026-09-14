# StreamMind

StreamMind is an AI-powered video knowledge and streaming platform. The initial vertical slice provides user authentication and an ownership-scoped video library; video upload and processing follow next.

## Local development

1. Copy `.env.example` to `.env` and replace `JWT_SECRET`.
2. Run `docker compose up --build`.
3. Open the frontend at `http://localhost:5173` and the API docs at `http://localhost:8000/docs`.

The backend runs database migrations before starting. Run tests with `docker compose run --rm backend pytest`.

## First API flow

1. `POST /auth/register`
2. `POST /auth/login` to receive a bearer token.
3. Use that token with `POST /videos` and `GET /videos`.

## Direct video uploads

The upload API uses an S3 presigned POST so video bytes travel directly from the
browser to S3 instead of through FastAPI:

1. Configure `AWS_REGION`, `S3_UPLOAD_BUCKET`, and AWS credentials in `.env`.
2. Configure that private bucket's CORS policy to allow `POST` from
   `http://localhost:5173` during local development.
3. `POST /videos/upload-url` with the title, filename, content type, and exact
   file size.
4. Submit the returned form fields and file to the returned S3 URL.
5. `POST /videos/{id}/complete-upload`; the API verifies the object with S3
   before changing its state to `UPLOADED`.

Accepted formats are MP4, QuickTime/MOV, and WebM. The default size limit is
2 GiB and presigned forms expire after 15 minutes. The bucket must remain private;
the presigned form grants narrowly scoped, temporary upload access.

## Project layout

- `frontend/`: React + TypeScript UI
- `backend/`: FastAPI API, database models, migrations, and tests
- `infra/`: planned AWS CDK application
- `workers/`: planned asynchronous video and AI processing workers

The detailed project plan is currently maintained in the workspace-level `../plan.md` and should be committed into this repository before the first push.
