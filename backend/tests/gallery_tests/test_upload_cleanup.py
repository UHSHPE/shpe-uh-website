import asyncio
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from routes import gallery_routes


def test_failed_database_commit_removes_uploaded_file(tmp_path, monkeypatch):
    class FailingSession:
        rolled_back = False

        def add(self, photo):
            pass

        def commit(self):
            raise RuntimeError("database unavailable")

        def rollback(self):
            self.rolled_back = True

    monkeypatch.setattr(gallery_routes, "GALLERY_IMAGE_DIR", tmp_path)
    session = FailingSession()
    file = UploadFile(
        file=BytesIO(b"\x89PNG\r\n\x1a\nimage data"),
        filename="photo.png",
        headers=Headers({"content-type": "image/png"}),
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        asyncio.run(gallery_routes.submit_photo(SimpleNamespace(id=1), session, file))

    assert session.rolled_back
    assert list(tmp_path.iterdir()) == []
