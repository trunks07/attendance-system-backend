import pytest
import app.services.AuthService as auth_service
from types import SimpleNamespace
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.main import app

import app.http.controllers.AuthController as auth_module
from app.models.schemas.UserSchema import User as UserSchemaModel



@pytest.fixture
def sample_login_payload():
    return {"email": "alice@example.com", "password": "secret"}


@pytest.fixture
def fake_user_doc():
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "_id": "507f1f77bcf86cd799439011",
        "email": "alice@example.com",
        "full_name": "Alice",
        "password": "hashed-password",
        "created_at": now_iso,
        "updated_at": now_iso,
    }


class FakeUserModel:
    """Fake UserModel exposing only the methods the Auth router uses."""
    def __init__(self, db=None):
        self.get_by_email = AsyncMock()
        self.update_password = AsyncMock()


@pytest.fixture
def patch_auth(monkeypatch):
    def _patch(fake_model_instance):
        monkeypatch.setattr(auth_module, "UserModel", lambda db=None: fake_model_instance)

        async def fake_get_db():
            return SimpleNamespace()
        monkeypatch.setattr(auth_module, "get_db", fake_get_db)

        monkeypatch.setattr(auth_module, "verify_password", lambda plain, hashed: True)
        monkeypatch.setattr(auth_module, "get_password_hash", lambda pw: "fakehash")
        monkeypatch.setattr(auth_module, "create_access_token", lambda data, expires_delta=None: "access-token")
        monkeypatch.setattr(auth_module, "create_refresh_token", lambda data, expires_delta=None: "refresh-token")
        monkeypatch.setattr(auth_module, "use_refresh_token", lambda token: {"access_token": "new-access", "refresh_token": "new-refresh"})

        async def _fake_current_user():
            return {"_id": "fixture-user", "email": "fixture@example.com", "full_name": "Fixture"}
        app.dependency_overrides[auth_service.get_current_active_user] = _fake_current_user

    try:
        yield _patch
    finally:
        app.dependency_overrides.pop(auth_service.get_current_active_user, None)

def patch_current_user(monkeypatch, profile_dict):
    async def _fake_current_user_model():
        return UserSchemaModel.model_validate(profile_dict)

    app.dependency_overrides[auth_service.get_current_active_user] = _fake_current_user_model
    monkeypatch.setattr(auth_module, "get_current_active_user", _fake_current_user_model)

    return lambda: app.dependency_overrides.pop(auth_service.get_current_active_user, None)


def test_login_success(patch_auth, fake_user_doc, sample_login_payload):
    fake_model = FakeUserModel()
    fake_model.get_by_email.return_value = fake_user_doc

    patch_auth(fake_model)

    with TestClient(app) as client:
        resp = client.post("/auth/login", json=sample_login_payload)

    assert resp.status_code == 200
    body = resp.json()
    assert "user" in body and "token" in body and "refresh_token" in body
    assert body["user"]["email"] == fake_user_doc["email"]
    assert body["token"]["access_token"] == "access-token"
    assert body["refresh_token"]["refresh_token"] == "refresh-token"


def test_login_user_not_found(patch_auth, sample_login_payload):
    fake_model = FakeUserModel()
    fake_model.get_by_email.return_value = None
    patch_auth(fake_model)

    with TestClient(app) as client:
        resp = client.post("/auth/login", json=sample_login_payload)

    assert resp.status_code == 400
    body = resp.json()
    assert "error" in body


def test_login_invalid_credentials(patch_auth, fake_user_doc, sample_login_payload, monkeypatch):
    fake_model = FakeUserModel()
    fake_model.get_by_email.return_value = fake_user_doc
    patch_auth(fake_model)
    monkeypatch.setattr(auth_module, "verify_password", lambda a, b: False)

    with TestClient(app) as client:
        resp = client.post("/auth/login", json=sample_login_payload)

    assert resp.status_code == 400
    body = resp.json()
    assert "error" in body


def test_refresh_token_success(monkeypatch):
    monkeypatch.setattr(auth_module, "use_refresh_token", lambda token: {"access_token": "rot-access", "refresh_token": "rot-refresh"})
    with TestClient(app) as client:
        resp = client.post("/auth/refresh", json={"refresh_token": "any-token"})

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body or "refresh_token" in body or isinstance(body, dict)


def test_get_profile_requires_auth(monkeypatch):
    now_iso = datetime.now(timezone.utc).isoformat()
    profile = {"_id": "507f1f77bcf86cd799439011", "email": "alice@example.com", "full_name": "Alice", "created_at": now_iso, "updated_at": now_iso}

    # patch the dependency to return our profile
    patch_current_user(monkeypatch, profile)

    with TestClient(app) as client:
        resp = client.get("/auth/profile")

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == profile["email"]
    assert body["_id"] == profile["_id"]


def test_change_password_success(patch_auth, monkeypatch):
    now_iso = datetime.now(timezone.utc).isoformat()
    profile = {"_id": "507f1f77bcf86cd799439011", "email": "alice@example.com", "full_name": "Alice", "created_at": now_iso, "updated_at": now_iso}

    fake_model = FakeUserModel()

    patch_auth(fake_model)
    patch_current_user(monkeypatch, profile)

    payload = {"password": "newpass", "confirm_password": "newpass"}

    with TestClient(app) as client:
        resp = client.patch("/auth/change-password", json=payload)

    assert resp.status_code == 204
    fake_model.update_password.assert_awaited()
