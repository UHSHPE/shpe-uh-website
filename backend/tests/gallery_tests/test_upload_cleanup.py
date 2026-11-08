import asyncio
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import UploadFile
from starlette.requests import Request
from starlette.datastructures import Headers

from routes import gallery_routes
from services import gallery_services
from tests.gallery_tests.helpers import make_png_bytes


def test_failed_database_commit_removes_uploaded_file(tmp_path, monkeypatch):
    class FailingSession:
        rolled_back = False
        next_id = 1

        class Result:
            def one(self):
                return SimpleNamespace(id=1)

        def exec(self, statement):
            return self.Result()

        def add(self, record):
            if getattr(record, "id", None) is None:
                record.id = self.next_id
                self.next_id += 1

        def flush(self):
            pass

        def commit(self):
            raise RuntimeError("database unavailable")

        def rollback(self):
            self.rolled_back = True

    monkeypatch.setattr(gallery_services, "GALLERY_IMAGE_DIR", tmp_path)
    monkeypatch.setattr(gallery_routes, "count_user_submissions_per_week", lambda *_: 0)
    session = FailingSession()
    file = UploadFile(
        file=BytesIO(make_png_bytes()),
        filename="photo.png",
        headers=Headers({"content-type": "image/png"}),
    )
    request = Request({"type": "http", "method": "POST", "path": "/gallery/photos", "headers": []})

    with pytest.raises(RuntimeError, match="database unavailable"):
        asyncio.run(
            gallery_routes.submit_photo.__wrapped__(
                request, SimpleNamespace(id=1), session, [file]
            )
        )

    assert session.rolled_back
    assert list(tmp_path.iterdir()) == []


def test_partial_upload_failure_removes_files_and_propagates_error(tmp_path, monkeypatch):
    first_path = tmp_path / "first.png"
    upload_count = 0

    async def failing_upload(file, contents):
        nonlocal upload_count
        upload_count += 1
        if upload_count == 2:
            raise OSError("disk unavailable")

        first_path.write_bytes(contents)
        return first_path.name, first_path

    monkeypatch.setattr(gallery_services, "upload_photo_file", failing_upload)

    with pytest.raises(OSError, match="disk unavailable"):
        asyncio.run(
            gallery_services.upload_photos(
                [
                    (SimpleNamespace(), b"first"),
                    (SimpleNamespace(), b"second"),
                ]
            )
        )

    assert list(tmp_path.iterdir()) == []
