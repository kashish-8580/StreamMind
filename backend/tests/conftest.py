import os
import tempfile

import pytest
from fastapi.testclient import TestClient

test_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
test_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{test_db.name}"
os.environ["JWT_SECRET"] = "test-secret"

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.storage import ObjectNotFoundError, get_storage  # noqa: E402


class FakeStorage:
    def __init__(self):
        self.objects = {}

    def create_upload(self, object_key, content_type, file_size):
        return {
            "url": "https://uploads.example.test",
            "fields": {"key": object_key, "Content-Type": content_type},
        }

    def inspect_object(self, object_key):
        if object_key not in self.objects:
            raise ObjectNotFoundError(object_key)
        return self.objects[object_key]


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def storage():
    fake = FakeStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_storage, None)
