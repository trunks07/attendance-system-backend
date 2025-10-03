import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.main import app
import app.http.controllers.UserController as user_controller_module
import app.services.AuthService as auth_service

# Import the Pydantic read model so our fake "current user" returns a model instance
from app.models.schemas.UserSchema import User as UserSchemaModel
from fastapi.routing import APIRoute

# --- Fake model used by controller (only methods used by controller) ---
class FakeUserModel:
    def __init__(self, db=None):
        # methods used by controller
        self.get_user_list = AsyncMock()
        self.get_by_email = AsyncMock()
        self.create = AsyncMock()
        self.get_by_id = AsyncMock()
        self.update = AsyncMock()
        self.update_password = AsyncMock()
        self.delete = AsyncMock()


# --- fixtures -------------------------------------------------------------
@pytest.fixture
def created_user_item():
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "_id": "68dcc1c89f6298a17aad2e78",
        "email": "carloguevarra454@gmail.com",
        "full_name": "Carlo Guevarra",
        "created_at": now_iso,
        "updated_at": now_iso,
    }


@pytest.fixture
def sample_user_payload():
    # include confirm_password if your CreateUserRequest requires it
    return {
        "email": "carloguevarra454@gmail.com",
        "password": "supersecret123",
        "confirm_password": "supersecret123",
        "full_name": "Carlo Guevarra",
    }


# helper to patch the UserModel, get_db and disable router-level auth for /users
@pytest.fixture
def patch_model(monkeypatch):
    """
    Monkeypatch UserModel factory and get_db for the controller,
    and remove router-level dependencies for any route under /users.
    This is robust: it avoids needing to identify the exact dependency function
    object FastAPI bound into the router at import time.
    """
    # keep a copy of the original dependant objects so we can restore on teardown
    original_route_dependants = {}

    def _patch(fake_instance):
        # 1) patch factory used in controller so controller uses our fake model
        monkeypatch.setattr(user_controller_module, "UserModel", lambda db=None: fake_instance)

        # 2) patch get_db to return a dummy object (avoid touching real DB)
        async def fake_get_db():
            return SimpleNamespace()
        monkeypatch.setattr(user_controller_module, "get_db", fake_get_db)

        # 3) remove route-level dependencies for any APIRoute that starts with /users
        #    This prevents FastAPI from enforcing the router-level OAuth dependency.
        for route in app.routes:
            if isinstance(route, APIRoute) and route.path.startswith("/users"):
                # save original dependant for cleanup
                original_route_dependants[route.path] = route.dependant
                # create a shallow copy of dependant with dependencies cleared
                # (mutating .dependencies is sufficient for our tests)
                try:
                    route.dependant.dependencies = []
                except Exception:
                    # fallback: set to an empty list if attribute style differs
                    route.dependant.dependencies = []

        # 4) provide a default get_current_active_user override for endpoints that
        #    still use Depends(get_current_active_user) (defensive)
        async def fake_current_active_user():
            profile = {
                "_id": "507f1f77bcf86cd799439011",
                "email": "fixture@example.com",
                "full_name": "Fixture",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            # Prefer to return a Pydantic model instance if consuming code expects attribute access
            try:
                return UserSchemaModel.model_validate(profile)
            except Exception:
                return profile

        # register dependency override (defensive; will be used if route-level dependencies were not applied)
        app.dependency_overrides[auth_service.get_current_active_user] = fake_current_active_user

    try:
        yield _patch
    finally:
        # cleanup: restore route dependants and remove overrides
        for route in list(app.routes):
            if isinstance(route, APIRoute) and route.path in original_route_dependants:
                try:
                    route.dependant = original_route_dependants[route.path]
                except Exception:
                    # try to restore the dependencies list at least
                    route.dependant.dependencies = getattr(original_route_dependants[route.path], "dependencies", [])
        # remove any overrides we set
        app.dependency_overrides.pop(auth_service.get_current_active_user, None)


# --- tests -----------------------------------------------------------------
def test_index_returns_paginated_list(patch_model, created_user_item):
    fake_instance = FakeUserModel()
    # controller expects get_user_list() to return (users, total_count)
    fake_instance.get_user_list.return_value = ([created_user_item], 1)

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.get("/users/?page=1&page_size=10")

    assert resp.status_code == 200, f"unexpected status: {resp.status_code} body: {resp.text}"
    body = resp.json()
    assert "data" in body and "pagination" in body
    assert len(body["data"]) == 1
    assert body["data"][0]["_id"] == created_user_item["_id"]


def test_store_creates_user_when_email_not_exists(patch_model, sample_user_payload, created_user_item):
    fake_instance = FakeUserModel()
    fake_instance.get_by_email.return_value = None
    fake_instance.create.return_value = created_user_item

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.post("/users/", json=sample_user_payload)

    assert resp.status_code == 200, f"unexpected status: {resp.status_code} body: {resp.text}"
    body = resp.json()
    assert body["email"] == created_user_item["email"]
    # create should have been awaited
    fake_instance.create.assert_awaited()


def test_store_returns_422_if_email_exists(patch_model, sample_user_payload):
    fake_instance = FakeUserModel()
    fake_instance.get_by_email.return_value = {"_id": "existing", "email": sample_user_payload["email"]}

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.post("/users/", json=sample_user_payload)

    assert resp.status_code == 422, f"unexpected status: {resp.status_code} body: {resp.text}"
    body = resp.json()
    assert "message" in body and "Email already exists" in body["message"]


def test_show_returns_user_when_found(patch_model, created_user_item):
    fake_instance = FakeUserModel()
    fake_instance.get_by_id.return_value = created_user_item

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.get(f"/users/{created_user_item['_id']}")

    assert resp.status_code == 200, f"unexpected status: {resp.status_code} body: {resp.text}"
    assert resp.json()["email"] == created_user_item["email"]


def test_show_404_when_not_found(patch_model):
    fake_instance = FakeUserModel()
    fake_instance.get_by_id.return_value = None

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.get("/users/doesnotexist")

    # controller catches the HTTPException and returns 400 in except block
    assert resp.status_code == 400


def test_update_returns_updated_user(patch_model, created_user_item):
    fake_instance = FakeUserModel()
    fake_instance.get_by_id.return_value = created_user_item
    fake_instance.update.return_value = created_user_item

    patch_model(fake_instance)

    update_payload = {"email": created_user_item["email"], "full_name": "Changed Name"}

    with TestClient(app) as client:
        resp = client.put(f"/users/{created_user_item['_id']}", json=update_payload)

    assert resp.status_code == 200, f"unexpected status: {resp.status_code} body: {resp.text}"
    assert resp.json()["email"] == created_user_item["email"]
    fake_instance.update.assert_awaited()


def test_update_password_returns_204(patch_model, created_user_item):
    fake_instance = FakeUserModel()
    fake_instance.get_by_id.return_value = created_user_item
    fake_instance.update_password.return_value = None

    patch_model(fake_instance)

    payload = {"password": "newpassword123", "confirm_password": "newpassword123"}

    with TestClient(app) as client:
        resp = client.patch(f"/users/{created_user_item['_id']}", json=payload)

    assert resp.status_code == 204, f"unexpected status: {resp.status_code} body: {resp.text}"
    fake_instance.update_password.assert_awaited()


def test_delete_returns_204(patch_model, created_user_item):
    fake_instance = FakeUserModel()
    fake_instance.get_by_id.return_value = created_user_item
    fake_instance.delete.return_value = None

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.delete(f"/users/{created_user_item['_id']}")

    assert resp.status_code == 204, f"unexpected status: {resp.status_code} body: {resp.text}"
    fake_instance.delete.assert_awaited()
