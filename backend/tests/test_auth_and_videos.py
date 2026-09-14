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


def test_user_can_request_and_complete_an_upload(client, storage):
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
    assert completed.json()["status"] == "UPLOADED"
    assert completed.json()["uploaded_file_size"] == 1234


def test_upload_rejects_unsupported_media_type(client, storage):
    token = register(client)
    response = client.post(
        "/videos/upload-url",
        headers=headers(token),
        json={"title": "Not a video", "filename": "payload.exe", "content_type": "application/octet-stream", "file_size": 10},
    )
    assert response.status_code == 415
