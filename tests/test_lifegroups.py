import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from fastapi.routing import APIRoute

from app.main import app
import app.http.controllers.LifegroupController as lifegroup_controller_module
import app.services.AuthService as auth_service


# --- Fake model for controller ---
class FakeLifegroupModel:
    def __init__(self, db=None):
        # async methods used by controller
        self.get_lifegroup_list = AsyncMock()
        self.create = AsyncMock()
        self.get_full_details = AsyncMock()
        self.get_by_id = AsyncMock()
        self.update = AsyncMock()
        self.delete = AsyncMock()


# --- fixtures -------------------------------------------------------------
@pytest.fixture
def created_lifegroup_item():
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "_id": "68e111111111111111111111",
        "name": "Test Lifegroup",
        "description": "Test Lifegroup decription",
        "members": ["68e000000000000000000111"],
        "tribe_id": "68e000000000000000000000",
        "leader_id": "68e000000000000000000111",
        "created_at": now_iso,
        "updated_at": now_iso,
    }


@pytest.fixture
def sample_lifegroup_payload():
    return {
        "name": "New Lifegroup",
        "description": "Test Lifegroup decription",
        "tribe_id": "68e000000000000000000000",
        "leader_id": "68e000000000000000000111",
    }


@pytest.fixture
def patch_model(monkeypatch):
    """
    Monkeypatch LifegroupModel factory, get_db and disable router auth dependencies.
    """
    original_route_dependants = {}

    def _patch(fake_instance):
        # patch LifegroupModel factory used by the controller module (important)
        monkeypatch.setattr(
            lifegroup_controller_module,
            "LifegroupModel",
            lambda db=None: fake_instance
        )

        # Also patch module-level model (optional but safe)
        monkeypatch.setattr("app.models.Lifegroup.LifegroupModel", lambda db=None: fake_instance)

        # patch get_db to return a simple namespace object (controller won't call real DB because model is faked)
        async def fake_get_db():
            return SimpleNamespace()
        monkeypatch.setattr(lifegroup_controller_module, "get_db", fake_get_db)

        # disable verify_token on /lifegroups routes
        for route in app.routes:
            if isinstance(route, APIRoute) and route.path.startswith("/lifegroups"):
                original_route_dependants[route.path] = route.dependant
                try:
                    route.dependant.dependencies = []
                except Exception:
                    route.dependant.dependencies = []

        # fallback get_current_active_user
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
        # restore dependants
        for route in list(app.routes):
            if isinstance(route, APIRoute) and route.path in original_route_dependants:
                try:
                    route.dependant = original_route_dependants[route.path]
                except Exception:
                    route.dependant.dependencies = getattr(original_route_dependants[route.path], "dependencies", [])
        app.dependency_overrides.pop(auth_service.get_current_active_user, None)


# --- tests ----------------------------------------------------------------
def test_index_returns_paginated_list(patch_model, created_lifegroup_item):
    fake_instance = FakeLifegroupModel()
    fake_instance.get_lifegroup_list.return_value = ([created_lifegroup_item], 1)

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.get("/lifegroups/?page=1&page_size=10")

    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert body["data"][0]["_id"] == created_lifegroup_item["_id"]


def test_store_creates_lifegroup(patch_model, sample_lifegroup_payload, created_lifegroup_item):
    fake_instance = FakeLifegroupModel()
    fake_instance.create.return_value = created_lifegroup_item

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.post("/lifegroups/", json=sample_lifegroup_payload)

    print(resp.json())
    assert resp.status_code == 201
    body = resp.json()
    assert body["_id"] == created_lifegroup_item["_id"]
    fake_instance.create.assert_awaited()


def test_show_returns_lifegroup(patch_model, created_lifegroup_item):
    fake_instance = FakeLifegroupModel()
    fake_instance.get_full_details.return_value = created_lifegroup_item

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.get(f"/lifegroups/{created_lifegroup_item['_id']}")

    assert resp.status_code == 200
    assert resp.json() == created_lifegroup_item


def test_show_404_when_not_found(patch_model):
    fake_instance = FakeLifegroupModel()
    fake_instance.get_full_details.return_value = None

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.get("/lifegroups/68df53d345febe98a9137288")

    assert resp.status_code == 404


def test_update_returns_updated_lifegroup(patch_model, created_lifegroup_item):
    fake_instance = FakeLifegroupModel()
    fake_instance.get_by_id.return_value = created_lifegroup_item
    fake_instance.update.return_value = created_lifegroup_item

    patch_model(fake_instance)

    payload = {
        "name": "Updated Lifegroup",
        "members": created_lifegroup_item["members"],
    }

    with TestClient(app) as client:
        resp = client.put(f"/lifegroups/{created_lifegroup_item['_id']}", json=payload)

    assert resp.status_code == 200
    assert resp.json() == created_lifegroup_item
    fake_instance.update.assert_awaited()


def test_update_404_when_not_found(patch_model):
    fake_instance = FakeLifegroupModel()
    fake_instance.get_by_id.return_value = None

    patch_model(fake_instance)

    payload = {"name": "Doesn't matter", "members": []}

    with TestClient(app) as client:
        resp = client.put("/lifegroups/68df53d345febe98a9137288", json=payload)

    assert resp.status_code == 404


def test_delete_returns_204(patch_model, created_lifegroup_item):
    fake_instance = FakeLifegroupModel()
    fake_instance.get_by_id.return_value = created_lifegroup_item
    fake_instance.delete.return_value = None

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.delete(f"/lifegroups/{created_lifegroup_item['_id']}")

    assert resp.status_code == 204
    fake_instance.delete.assert_awaited()


def test_delete_404_when_not_found(patch_model):
    fake_instance = FakeLifegroupModel()
    fake_instance.get_by_id.return_value = None

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.delete("/lifegroups/68df53d345febe98a9137288")

    assert resp.status_code == 404


def test_set_members_returns_updated_lifegroup(patch_model, created_lifegroup_item):
    fake_instance = FakeLifegroupModel()
    fake_instance.get_by_id.return_value = created_lifegroup_item
    fake_instance.update.return_value = created_lifegroup_item

    patch_model(fake_instance)

    payload = {"members": created_lifegroup_item["members"]}

    with TestClient(app) as client:
        resp = client.patch(f"/lifegroups/{created_lifegroup_item['_id']}", json=payload)

    assert resp.status_code == 200
    assert resp.json() == created_lifegroup_item
    fake_instance.update.assert_awaited()


def test_set_members_404_when_not_found(patch_model):
    fake_instance = FakeLifegroupModel()
    fake_instance.get_by_id.return_value = None

    patch_model(fake_instance)

    payload = {"members": []}

    with TestClient(app) as client:
        resp = client.patch("/lifegroups/68df53d345febe98a9137288", json=payload)

    assert resp.status_code == 404
