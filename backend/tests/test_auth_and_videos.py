import uuid


def register(client, email="person@example.com", password="correct-horse-battery"):
    response = client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201
    return response.json()["access_token"]


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_user_can_create_and_list_own_videos(client):
    token = register(client)
    created = client.post("/videos", headers=headers(token), json={"title": "Architecture talk"})
    assert created.status_code == 201
    assert created.json()["status"] == "DRAFT"

    listed = client.get("/videos", headers=headers(token))
    assert listed.status_code == 200
    assert [video["title"] for video in listed.json()] == ["Architecture talk"]


def test_user_cannot_read_another_users_video(client):
    first_token = register(client, "first@example.com")
    video_id = client.post("/videos", headers=headers(first_token), json={"title": "Private video"}).json()["id"]
    second_token = register(client, "second@example.com")

    response = client.get(f"/videos/{video_id}", headers=headers(second_token))
    assert response.status_code == 404


def test_ready_video_returns_signed_playback_manifest(client, storage):
    from app.database import SessionLocal
    from app.models import Video

    token = register(client)
    created = client.post("/videos", headers=headers(token), json={"title": "Ready video"}).json()
    manifest_key = f"users/user/videos/{created['id']}/hls/index.m3u8"
    with SessionLocal() as db:
        video = db.get(Video, uuid.UUID(created["id"]))
        video.status = "STREAM_READY"
        video.hls_manifest_key = manifest_key
        video.thumbnail_key = f"users/user/videos/{created['id']}/thumbnail.jpg"
        db.commit()
    storage.processed_text[manifest_key] = "#EXTM3U\n#EXTINF:2.0,\nsegment_00000.ts\n#EXT-X-ENDLIST\n"

    response = client.get(f"/videos/{created['id']}/playback", headers=headers(token))

    assert response.status_code == 200
    body = response.json()
    assert "https://media.example.test/users/user/videos/" in body["manifest"]
    assert "segment_00000.ts?signature=test" in body["manifest"]
    assert body["thumbnail_url"].endswith("thumbnail.jpg?signature=test")


def test_unready_video_cannot_be_played(client, storage):
    token = register(client)
    created = client.post("/videos", headers=headers(token), json={"title": "Not ready"}).json()

    response = client.get(f"/videos/{created['id']}/playback", headers=headers(token))

    assert response.status_code == 409


def test_user_can_request_and_complete_an_upload(client, storage, processing_queue):
    token = register(client)
    requested = client.post(
        "/videos/upload-url",
        headers=headers(token),
        json={
            "title": "Queue design",
            "filename": "talk.mp4",
            "content_type": "video/mp4",
            "file_size": 1234,
        },
    )
    assert requested.status_code == 201
    body = requested.json()
    assert body["video"]["status"] == "PENDING_UPLOAD"
    object_key = body["upload"]["fields"]["key"]
    storage.objects[object_key] = {
        "ContentLength": 1234,
        "ContentType": "video/mp4",
        "ETag": '"test-etag"',
    }

    completed = client.post(
        f"/videos/{body['video']['id']}/complete-upload",
        headers=headers(token),
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "QUEUED"
    assert completed.json()["uploaded_file_size"] == 1234
    assert processing_queue.messages[0]["video_id"] == body["video"]["id"]

    repeated = client.post(
        f"/videos/{body['video']['id']}/complete-upload",
        headers=headers(token),
    )
    assert repeated.status_code == 200
    assert len(processing_queue.messages) == 1

    job_status = client.get(
        f"/videos/{body['video']['id']}/status",
        headers=headers(token),
    )
    assert job_status.status_code == 200
    assert job_status.json()["processing_job"]["status"] == "QUEUED"


def test_upload_rejects_unsupported_media_type(client, storage):
    token = register(client)
    response = client.post(
        "/videos/upload-url",
        headers=headers(token),
        json={"title": "Not a video", "filename": "payload.exe", "content_type": "application/octet-stream", "file_size": 10},
    )
    assert response.status_code == 415


def test_queue_failure_preserves_upload_and_pending_job(client, storage, processing_queue):
    token = register(client)
    requested = client.post(
        "/videos/upload-url",
        headers=headers(token),
        json={
            "title": "Retryable upload",
            "filename": "retry.mp4",
            "content_type": "video/mp4",
            "file_size": 50,
        },
    ).json()
    storage.objects[requested["upload"]["fields"]["key"]] = {
        "ContentLength": 50,
        "ContentType": "video/mp4",
        "ETag": '"retry-etag"',
    }
    processing_queue.available = False

    failed = client.post(
        f"/videos/{requested['video']['id']}/complete-upload",
        headers=headers(token),
    )
    assert failed.status_code == 503

    status_after_failure = client.get(
        f"/videos/{requested['video']['id']}/status",
        headers=headers(token),
    ).json()
    assert status_after_failure["video_status"] == "UPLOADED"
    assert status_after_failure["processing_job"]["status"] == "PENDING"

    processing_queue.available = True
    retried = client.post(
        f"/videos/{requested['video']['id']}/complete-upload",
        headers=headers(token),
    )
    assert retried.status_code == 200
    assert retried.json()["status"] == "QUEUED"
    assert len(processing_queue.messages) == 1
