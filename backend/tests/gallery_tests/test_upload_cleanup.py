import asyncio
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import UploadFile
from starlette.requests import Request
from starlette.datastructures import Headers

from routes import gallery_routes
from services import gallery_services


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
        file=BytesIO(b"\x89PNG\r\n\x1a\nimage data"),
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
