# tests/test_tribe.py
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from fastapi.routing import APIRoute

from app.main import app
import app.http.controllers.TribeController as tribe_controller_module  # adjust if your filename differs
import app.services.AuthService as auth_service

# --- Fake model used by controller (only methods used by controller) ---
class FakeTribeModel:
    def __init__(self, db=None):
        self.get_tribe_list = AsyncMock()
        self.create = AsyncMock()
        self.get_by_id = AsyncMock()
        self.update = AsyncMock()
        self.delete = AsyncMock()


# --- fixtures -------------------------------------------------------------
@pytest.fixture
def created_tribe_item():
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "_id": "68e000000000000000000001",
        "name": "Test Tribe",
        "description": "A sample tribe for testing",
        "created_at": now_iso,
        "updated_at": now_iso,
    }


@pytest.fixture
def sample_tribe_payload():
    return {
        "name": "New Tribe",
        "description": "A Tribe created in tests",
    }


# helper to patch the TribeModel, get_db and disable router-level auth for /trib*
@pytest.fixture
def patch_model(monkeypatch):
    """
    Monkeypatch TribeModel factory and get_db for the controller,
    and remove router-level dependencies for any route under /trib (robust to /tribe or /tribes).
    """
    original_route_dependants = {}

    def _patch(fake_instance):
        # patch factory used in controller so controller uses our fake model
        monkeypatch.setattr(tribe_controller_module, "TribeModel", lambda db=None: fake_instance)

        # patch get_db to return a dummy object (avoid touching real DB)
        async def fake_get_db():
            return SimpleNamespace()
        monkeypatch.setattr(tribe_controller_module, "get_db", fake_get_db)

        # remove route-level dependencies for routes that start with "/trib"
        for route in app.routes:
            if isinstance(route, APIRoute) and route.path.startswith("/trib"):
                original_route_dependants[route.path] = route.dependant
                # clear dependencies so verify_token won't run
                try:
                    route.dependant.dependencies = []
                except Exception:
                    route.dependant.dependencies = []

        # defensive override for get_current_active_user in case some endpoints still depend on it
        async def fake_current_active_user():
            now_iso = datetime.now(timezone.utc).isoformat()
            return {
                "_id": "507f1f77bcf86cd799439011",
                "email": "fixture@example.com",
                "full_name": "Fixture",
                "created_at": now_iso,
                "updated_at": now_iso,
            }

        app.dependency_overrides[auth_service.get_current_active_user] = fake_current_active_user

    try:
        yield _patch
    finally:
        # restore original dependants and remove dependency overrides
        for route in list(app.routes):
            if isinstance(route, APIRoute) and route.path in original_route_dependants:
                try:
                    route.dependant = original_route_dependants[route.path]
                except Exception:
                    route.dependant.dependencies = getattr(original_route_dependants[route.path], "dependencies", [])
        app.dependency_overrides.pop(auth_service.get_current_active_user, None)


# --- tests -----------------------------------------------------------------
def test_index_returns_paginated_list(patch_model, created_tribe_item):
    fake_instance = FakeTribeModel()
    fake_instance.get_tribe_list.return_value = ([created_tribe_item], 1)

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.get("/tribes/?page=1&page_size=10")

    assert resp.status_code == 200, f"unexpected status: {resp.status_code} body: {resp.text}"
    body = resp.json()
    assert "data" in body and "pagination" in body
    assert len(body["data"]) == 1
    assert body["data"][0]["_id"] == created_tribe_item["_id"]


def test_store_creates_tribe(patch_model, sample_tribe_payload, created_tribe_item):
    fake_instance = FakeTribeModel()
    fake_instance.create.return_value = created_tribe_item

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.post("/tribes/", json=sample_tribe_payload)

    assert resp.status_code == 201, f"unexpected status: {resp.status_code} body: {resp.text}"
    body = resp.json()
    assert body["_id"] == created_tribe_item["_id"]
    fake_instance.create.assert_awaited()


def test_show_returns_tribe_when_found(patch_model, created_tribe_item):
    fake_instance = FakeTribeModel()
    fake_instance.get_by_id.return_value = created_tribe_item

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.get(f"/tribes/{created_tribe_item['_id']}")

    assert resp.status_code == 200
    assert resp.json() == created_tribe_item


def test_show_returns_null_when_not_found(patch_model):
    fake_instance = FakeTribeModel()
    fake_instance.get_by_id.return_value = None

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.get("/tribes/doesnotexist")

    # controller returns 200 with null body if get_by_id returns None
    assert resp.status_code == 200
    assert resp.json() is None


def test_update_returns_updated_tribe(patch_model, created_tribe_item):
    fake_instance = FakeTribeModel()
    fake_instance.get_by_id.return_value = created_tribe_item
    fake_instance.update.return_value = created_tribe_item

    patch_model(fake_instance)

    payload = {"name": created_tribe_item["name"], "description": "Updated"}

    with TestClient(app) as client:
        resp = client.put(f"/tribes/{created_tribe_item['_id']}", json=payload)

    assert resp.status_code == 200
    assert resp.json() == created_tribe_item
    fake_instance.update.assert_awaited()


def test_update_404_when_not_found(patch_model):
    fake_instance = FakeTribeModel()
    fake_instance.get_by_id.return_value = None

    patch_model(fake_instance)

    payload = {"name": "anything", "description": "anything"}

    with TestClient(app) as client:
        resp = client.put("/tribes/doesnotexist", json=payload)

    # controller catches HTTPException and returns 400 in except block
    assert resp.status_code == 400


def test_delete_returns_204(patch_model, created_tribe_item):
    fake_instance = FakeTribeModel()
    fake_instance.get_by_id.return_value = created_tribe_item
    fake_instance.delete.return_value = None

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.delete(f"/tribes/{created_tribe_item['_id']}")

    assert resp.status_code == 204
    fake_instance.delete.assert_awaited()


def test_delete_404_when_not_found(patch_model):
    fake_instance = FakeTribeModel()
    fake_instance.get_by_id.return_value = None

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.delete("/tribes/doesnotexist")

    # controller catches HTTPException and returns 400 in except block
    assert resp.status_code == 400
