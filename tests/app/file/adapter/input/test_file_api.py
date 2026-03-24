from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.file.application.exception import FileNotFoundException
from app.file.application.service.file import FileService
from app.file.domain.entity.file import File, FileStatus
from main import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def make_file(status: FileStatus = FileStatus.PENDING) -> File:
    return File(
        file_name="avatar.png",
        file_path="uploads/avatar.png",
        file_extension="png",
        file_size=1024,
        mime_type="image/png",
        status=status,
    )


def test_create_file_returns_serialized_id(client, monkeypatch):
    async def create_stub_file(*_args, **_kwargs):
        return make_file()

    monkeypatch.setattr(FileService, "create_file", create_stub_file)

    response = client.post(
        "/api/files",
        json={
            "file_name": "avatar.png",
            "file_path": "uploads/avatar.png",
            "file_extension": "png",
            "file_size": 1024,
            "mime_type": "image/png",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["data"]["id"], str)
    assert body["data"]["status"] == "pending"


def test_list_files_returns_200(client, monkeypatch):
    async def list_stub_files(*_args, **_kwargs):
        return [
            make_file(),
            File(
                file_name="resume.pdf",
                file_path="docs/resume.pdf",
                file_extension="pdf",
                file_size=2048,
                mime_type="application/pdf",
            ),
        ]

    monkeypatch.setattr(FileService, "list_files", list_stub_files)

    response = client.get("/api/files")

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 2
    assert body["data"][1]["file_extension"] == "pdf"


def test_get_file_returns_200(client, monkeypatch):
    async def get_stub_file(*_args, **_kwargs):
        return make_file()

    monkeypatch.setattr(FileService, "get_file", get_stub_file)

    response = client.get(f"/api/files/{uuid4()}")

    assert response.status_code == 200
    assert response.json()["data"]["file_name"] == "avatar.png"


def test_get_file_not_found_returns_404(client, monkeypatch):
    async def raise_not_found(*_args, **_kwargs):
        raise FileNotFoundException()

    monkeypatch.setattr(FileService, "get_file", raise_not_found)

    response = client.get(f"/api/files/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error_code"] == "FILE__NOT_FOUND"


def test_update_file_returns_200(client, monkeypatch):
    async def update_stub_file(*_args, **_kwargs):
        return File(
            file_name="resume.pdf",
            file_path="docs/resume.pdf",
            file_extension="pdf",
            file_size=2048,
            mime_type="application/pdf",
            status=FileStatus.ACTIVE,
        )

    monkeypatch.setattr(FileService, "update_file", update_stub_file)

    response = client.patch(
        f"/api/files/{uuid4()}",
        json={
            "file_name": "resume.pdf",
            "mime_type": "application/pdf",
            "status": "active",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["file_name"] == "resume.pdf"
    assert response.json()["data"]["status"] == "active"


def test_delete_file_returns_200(client, monkeypatch):
    async def delete_stub_file(*_args, **_kwargs):
        return make_file(status=FileStatus.DELETED)

    monkeypatch.setattr(FileService, "delete_file", delete_stub_file)

    response = client.delete(f"/api/files/{uuid4()}")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "deleted"


@pytest.mark.parametrize(
    ("payload", "field_name"),
    [
        (
            {
                "file_name": "",
                "file_path": "uploads/avatar.png",
                "file_extension": "png",
                "file_size": 1024,
                "mime_type": "image/png",
            },
            "file_name",
        ),
        (
            {
                "file_name": "avatar.png",
                "file_path": "",
                "file_extension": "png",
                "file_size": 1024,
                "mime_type": "image/png",
            },
            "file_path",
        ),
        (
            {
                "file_name": "avatar.png",
                "file_path": "uploads/avatar.png",
                "file_extension": "png",
                "file_size": 0,
                "mime_type": "image/png",
            },
            "file_size",
        ),
    ],
)
def test_create_file_invalid_input_returns_422(client, payload, field_name):
    response = client.post("/api/files", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"
    assert any(
        field_name in ".".join(map(str, item.get("loc", [])))
        or field_name in str(item.get("msg", ""))
        for item in body["detail"]
    )


def test_update_file_invalid_input_returns_422(client):
    response = client.patch(f"/api/files/{uuid4()}", json={})

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"
