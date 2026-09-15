FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app HF_HOME=/models

COPY backend/requirements.txt /app/backend-requirements.txt
COPY workers/transcription/requirements.txt /app/transcription-requirements.txt
RUN pip install --no-cache-dir -r /app/backend-requirements.txt -r /app/transcription-requirements.txt
COPY backend/app /app/app
COPY workers/transcription /app/transcription

CMD ["python", "-m", "transcription.worker"]
