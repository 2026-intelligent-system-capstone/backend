from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.organization.application.exception import (
    OrganizationCodeAlreadyExistsException,
    OrganizationNotFoundException,
)
from app.organization.application.service import OrganizationService
from app.organization.domain.entity import (
    Organization,
    OrganizationAuthProvider,
)
from app.user.adapter.output.persistence.sqlalchemy import (
    UserSQLAlchemyRepository,
)
from app.user.domain.entity import User, UserRole
from core.config import config
from core.domain.types import TokenType
from core.helpers.token import TokenHelper
from main import create_app

HANSUNG_ID = UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def make_organization() -> Organization:
    organization = Organization(
        code="univ_hansung",
        name="한성대학교",
        auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
    )
    organization.id = HANSUNG_ID
    return organization


def make_user(role: UserRole = UserRole.STUDENT) -> User:
    return User(
        organization_id=HANSUNG_ID,
        login_id="admin01",
        role=role,
        email="admin@example.com",
        name="관리자",
    )


def set_access_token_cookie(client: TestClient, user: User) -> None:
    access_token = TokenHelper.create_token(
        payload={"sub": str(user.id)},
        token_type=TokenType.ACCESS,
    )
    client.cookies.set(config.ACCESS_TOKEN_COOKIE_NAME, access_token)


def test_list_organizations_returns_200(client, monkeypatch):
    async def list_stub_organizations(*_args, **_kwargs):
        return [make_organization()]

    monkeypatch.setattr(
        OrganizationService,
        "list_organizations",
        list_stub_organizations,
    )

    response = client.get("/api/organizations")

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["code"] == "univ_hansung"


def test_create_organization_returns_200(client, monkeypatch):
    async def create_stub_organization(*_args, **_kwargs):
        return make_organization()

    admin_user = make_user(role=UserRole.ADMIN)

    async def get_by_id_stub(*_args, **_kwargs):
        return admin_user

    monkeypatch.setattr(
        OrganizationService,
        "create_organization",
        create_stub_organization,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, admin_user)

    response = client.post(
        "/api/organizations",
        json={
            "code": "univ_hansung",
            "name": "한성대학교",
            "auth_provider": "hansung_sis",
            "is_active": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["code"] == "univ_hansung"


def test_create_organization_returns_403_for_non_admin(client, monkeypatch):
    student_user = make_user(role=UserRole.STUDENT)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.post(
        "/api/organizations",
        json={
            "code": "univ_hansung",
            "name": "한성대학교",
            "auth_provider": "hansung_sis",
            "is_active": True,
        },
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "AUTH__FORBIDDEN"


def test_get_organization_returns_200(client, monkeypatch):
    async def get_stub_organization(*_args, **_kwargs):
        return make_organization()

    monkeypatch.setattr(
        OrganizationService,
        "get_organization",
        get_stub_organization,
    )

    response = client.get(f"/api/organizations/{HANSUNG_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["id"] == str(HANSUNG_ID)
    assert body["data"]["auth_provider"] == "hansung_sis"


def test_update_organization_returns_200(client, monkeypatch):
    async def update_stub_organization(*_args, **_kwargs):
        organization = make_organization()
        organization.name = "한성대학교 테스트"
        organization.is_active = False
        return organization

    admin_user = make_user(role=UserRole.ADMIN)

    async def get_by_id_stub(*_args, **_kwargs):
        return admin_user

    monkeypatch.setattr(
        OrganizationService,
        "update_organization",
        update_stub_organization,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, admin_user)

    response = client.patch(
        f"/api/organizations/{HANSUNG_ID}",
        json={"name": "한성대학교 테스트", "is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "한성대학교 테스트"
    assert response.json()["data"]["is_active"] is False


def test_update_organization_returns_403_for_non_admin(client, monkeypatch):
    student_user = make_user(role=UserRole.STUDENT)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.patch(
        f"/api/organizations/{HANSUNG_ID}",
        json={"name": "한성대학교 테스트"},
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "AUTH__FORBIDDEN"


def test_get_organization_not_found_returns_404(client, monkeypatch):
    async def raise_not_found(*_args, **_kwargs):
        raise OrganizationNotFoundException()

    monkeypatch.setattr(
        OrganizationService,
        "get_organization",
        raise_not_found,
    )

    response = client.get(f"/api/organizations/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error_code"] == "ORGANIZATION__NOT_FOUND"


def test_delete_organization_returns_200(client, monkeypatch):
    async def delete_stub_organization(*_args, **_kwargs):
        organization = make_organization()
        organization.delete()
        return organization

    admin_user = make_user(role=UserRole.ADMIN)

    async def get_by_id_stub(*_args, **_kwargs):
        return admin_user

    monkeypatch.setattr(
        OrganizationService,
        "delete_organization",
        delete_stub_organization,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, admin_user)

    response = client.delete(f"/api/organizations/{HANSUNG_ID}")

    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is False


def test_delete_organization_returns_403_for_non_admin(client, monkeypatch):
    student_user = make_user(role=UserRole.STUDENT)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.delete(f"/api/organizations/{HANSUNG_ID}")

    assert response.status_code == 403
    assert response.json()["error_code"] == "AUTH__FORBIDDEN"


def test_get_organization_invalid_id_returns_422(client):
    response = client.get("/api/organizations/invalid-uuid")

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_create_organization_duplicate_code_returns_409(client, monkeypatch):
    async def raise_duplicate_code(*_args, **_kwargs):
        raise OrganizationCodeAlreadyExistsException()

    admin_user = make_user(role=UserRole.ADMIN)

    async def get_by_id_stub(*_args, **_kwargs):
        return admin_user

    monkeypatch.setattr(
        OrganizationService,
        "create_organization",
        raise_duplicate_code,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, admin_user)

    response = client.post(
        "/api/organizations",
        json={
            "code": "univ_hansung",
            "name": "한성대학교",
            "auth_provider": "hansung_sis",
        },
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "ORGANIZATION__CODE_ALREADY_EXISTS"


@pytest.mark.parametrize(
    ("payload", "field_name"),
    [
        (
            {
                "code": "",
                "name": "한성대학교",
                "auth_provider": "hansung_sis",
            },
            "code",
        ),
        (
            {
                "code": "univ_hansung",
                "name": "김",
                "auth_provider": "hansung_sis",
            },
            "name",
        ),
        (
            {
                "code": "univ_hansung",
                "name": "한성대학교",
                "auth_provider": "unknown",
            },
            "auth_provider",
        ),
    ],
)
def test_create_organization_invalid_input_returns_422(
    client,
    monkeypatch,
    payload,
    field_name,
):
    admin_user = make_user(role=UserRole.ADMIN)

    async def get_by_id_stub(*_args, **_kwargs):
        return admin_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, admin_user)

    response = client.post("/api/organizations", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"
    assert any(
        field_name in ".".join(map(str, item["loc"]))
        or field_name in item["msg"]
        for item in body["detail"]
    )


def test_update_organization_empty_payload_returns_422(client, monkeypatch):
    admin_user = make_user(role=UserRole.ADMIN)

    async def get_by_id_stub(*_args, **_kwargs):
        return admin_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, admin_user)

    response = client.patch(f"/api/organizations/{HANSUNG_ID}", json={})

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"
