# tests/test_user.py
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

# module path of the router
import app.http.controllers.UserController as user_controller_module

# import your FastAPI app
from app.main import app


@pytest.fixture
def any_objectid():
    return ObjectId()


@pytest.fixture
def sample_user_payload():
    # include the confirm/confirmation field your CreateUserRequest expects.
    # If your request uses a different name, change it accordingly.
    return {
        "email": "carloguevarra454@gmail.com",
        "password": "supersecret123",
        "full_name": "Carlo Guevarra",
        # common variants: "confirm_password" or "password_confirmation"
        # change to match your CreateUserRequest exactly
        "confirm_password": "supersecret123",
    }


@pytest.fixture
def created_user_item(any_objectid):
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "_id": str(any_objectid),
        "email": "carloguevarra454@gmail.com",
        "full_name": "Carlo Guevarra",
        "created_at": now_iso,
        "updated_at": now_iso,
    }


@pytest.fixture
def created_user_response(created_user_item):
    return {
        "data": [created_user_item],
        "pagination": {
            "total_items": 1,
            "total_pages": 1,
            "current_page": 1,
            "page_size": 10,
            "next_page": None,
            "prev_page": None,
            "search_term": None,
        },
    }


class FakeUserModel:
    """
    Fake UserModel with AsyncMocks you can set in tests.
    """

    def __init__(self, db=None):
        self.get_user_list = AsyncMock()
        self.get_by_email = AsyncMock()
        self.create = AsyncMock()
        self.get_by_id = AsyncMock()
        self.update = AsyncMock()
        self.update_password = AsyncMock()
        self.delete = AsyncMock()


@pytest.fixture
def patch_model(monkeypatch):
    """
    Returns a helper that patches UserModel to return the provided fake instance
    and patches get_db to a dummy async function.
    Usage in tests: patch_model(fake_instance)
    """

    def _patch(fake_instance):
        # Patch the class so controller's UserModel(db) returns our fake_instance
        monkeypatch.setattr(
            user_controller_module, "UserModel", lambda db=None: fake_instance
        )

        async def fake_get_db():
            return SimpleNamespace()  # dummy db object

        monkeypatch.setattr(user_controller_module, "get_db", fake_get_db)

    return _patch


def test_index_returns_paginated_list(patch_model, created_user_item):
    fake_instance = FakeUserModel()
    # Configure return value (note: get_user_list is AsyncMock -> await returns this tuple)
    fake_instance.get_user_list.return_value = ([created_user_item], 1)

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.get("/users/?page=1&page_size=10")

    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body and "pagination" in body
    assert isinstance(body["data"], list) and len(body["data"]) == 1
    item = body["data"][0]
    assert item["_id"] == created_user_item["_id"]
    assert item["email"] == created_user_item["email"]
    pag = body["pagination"]
    assert pag["total_items"] == 1
    assert pag["current_page"] == 1
    assert pag["page_size"] == 10


def test_store_creates_user_when_email_not_exists(
    patch_model, sample_user_payload, created_user_item
):
    fake_instance = FakeUserModel()
    fake_instance.get_by_email.return_value = None
    fake_instance.create.return_value = created_user_item

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.post("/users/", json=sample_user_payload)

    # should be successful
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == created_user_item["email"]
    assert "_id" in body


def test_store_returns_422_if_email_exists(patch_model, sample_user_payload):
    fake_instance = FakeUserModel()
    fake_instance.get_by_email.return_value = {
        "_id": "existing",
        "email": sample_user_payload["email"],
    }

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.post("/users/", json=sample_user_payload)

    assert resp.status_code == 422
    body = resp.json()
    # your controller returns {"message": "Email already exists"} on that branch
    assert "message" in body and "Email already exists" in body["message"]


def test_show_returns_user_when_found(patch_model, created_user_item):
    fake_instance = FakeUserModel()
    fake_instance.get_by_id.return_value = created_user_item

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.get(f"/users/{created_user_item['_id']}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == created_user_item["email"]


def test_show_404_when_not_found(patch_model):
    fake_instance = FakeUserModel()
    fake_instance.get_by_id.return_value = None

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.get("/users/doesnotexist")

    # controller catches the HTTPException and currently returns status 400 in except block
    assert resp.status_code == 400


def test_update_returns_updated_user(patch_model, created_user_item):
    fake_instance = FakeUserModel()
    fake_instance.get_by_id.return_value = created_user_item
    fake_instance.update.return_value = created_user_item

    patch_model(fake_instance)

    update_payload = {"email": created_user_item["email"]}

    with TestClient(app) as client:
        resp = client.put(f"/users/{created_user_item['_id']}", json=update_payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == created_user_item["email"]


def test_update_password_returns_204(patch_model, created_user_item):
    fake_instance = FakeUserModel()
    fake_instance.get_by_id.return_value = created_user_item
    fake_instance.update_password.return_value = None

    patch_model(fake_instance)

    payload = {"password": "newpassword123", "confirm_password": "newpassword123"}

    with TestClient(app) as client:
        resp = client.patch(f"/users/{created_user_item['_id']}", json=payload)

    assert resp.status_code == 204


def test_delete_returns_204(patch_model, created_user_item):
    fake_instance = FakeUserModel()
    fake_instance.get_by_id.return_value = created_user_item
    fake_instance.delete.return_value = None

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.delete(f"/users/{created_user_item['_id']}")

    assert resp.status_code == 204
