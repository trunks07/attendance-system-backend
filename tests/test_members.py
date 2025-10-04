import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from fastapi.routing import APIRoute

from app.main import app
import app.http.controllers.MemberController as member_controller_module
import app.services.AuthService as auth_service


# --- Fake model for controller ---
class FakeMemberModel:
    def __init__(self, db=None):
        self.get_member_list = AsyncMock()
        self.create = AsyncMock()
        self.get_member_full_details = AsyncMock()
        self.get_by_id = AsyncMock()
        self.update = AsyncMock()
        self.delete = AsyncMock()

class FakeLifegroupModel:
    def __init__(self, db=None):
        self.db = db

    async def get_lifegroup_by_member_id(self, member_id, include_deleted=False, session=None):
        return {"_id": "fake_lg_id", "members": [member_id]}

    async def update(self, lg_id, payload):
        return {"_id": lg_id, **(payload.__dict__ if hasattr(payload, "__dict__") else {})}


# --- fixtures -------------------------------------------------------------
@pytest.fixture
def created_member_item():
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "_id": "68e000000000000000000111",
        "tribe_id": "68e000000000000000000000",
        "first_name": "John",
        "last_name": "Doe",
        "middle_name": "X",
        "address": "123 Test St",
        "birthday": "1999-04-27",
        "created_at": now_iso,
        "updated_at": now_iso,
    }


@pytest.fixture
def sample_member_payload():
    return {
        "tribe_id": "68e000000000000000000000",
        "first_name": "Jane",
        "last_name": "Smith",
        "middle_name": "Y",
        "address": "456 Example Rd",
        "birthday": "1999-04-27"
    }


@pytest.fixture
def patch_model(monkeypatch):
    """
    Monkeypatch MemberModel factory, LifegroupModel used by the controller,
    get_db and disable router auth dependencies.
    """
    original_route_dependants = {}

    def _patch(fake_instance):
        # patch MemberModel factory used by the controller
        monkeypatch.setattr(
            member_controller_module,
            "MemberModel",
            lambda db=None: fake_instance
        )

        # patch LifegroupModel used by the controller (important — patch controller symbol)
        monkeypatch.setattr(
            member_controller_module,
            "LifegroupModel",
            lambda db=None: FakeLifegroupModel(db)
        )

        # Also patch the module-level LifegroupModel (optional but harmless)
        monkeypatch.setattr("app.models.Lifegroup.LifegroupModel", lambda db=None: FakeLifegroupModel(db))

        # patch get_db to return a simple namespace (controller won't call DB because models are faked)
        async def fake_get_db():
            return SimpleNamespace()
        monkeypatch.setattr(member_controller_module, "get_db", fake_get_db)

        # disable verify_token on /members routes (fix path check from "/member" -> "/members")
        for route in app.routes:
            if isinstance(route, APIRoute) and route.path.startswith("/members"):
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
def test_index_returns_paginated_list(patch_model, created_member_item):
    fake_instance = FakeMemberModel()
    fake_instance.get_member_list.return_value = ([created_member_item], 1)

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.get("/members/?page=1&page_size=10")

    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert body["data"][0]["_id"] == created_member_item["_id"]


def test_store_creates_member(patch_model, sample_member_payload, created_member_item):
    fake_instance = FakeMemberModel()
    fake_instance.create.return_value = created_member_item

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.post("/members/", json=sample_member_payload)

    assert resp.status_code == 201
    body = resp.json()
    assert body["_id"] == created_member_item["_id"]
    fake_instance.create.assert_awaited()


def test_show_returns_member(patch_model, created_member_item):
    fake_instance = FakeMemberModel()
    fake_instance.get_member_full_details.return_value = created_member_item

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.get(f"/members/{created_member_item['_id']}")

    assert resp.status_code == 200
    assert resp.json() == created_member_item


def test_show_404_when_not_found(patch_model):
    fake_instance = FakeMemberModel()
    fake_instance.get_member_full_details.return_value = None

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.get("/members/68df53d345febe98a9137288")

    assert resp.status_code == 404  # controller wraps 404 into 400 response


def test_update_returns_updated_member(patch_model, created_member_item):
    fake_instance = FakeMemberModel()
    fake_instance.get_by_id.return_value = created_member_item
    fake_instance.update.return_value = created_member_item

    patch_model(fake_instance)

    payload = {
        "first_name": created_member_item["first_name"],
        "last_name": "Updated",
        "middle_name": created_member_item["middle_name"],
        "address": created_member_item["address"],
    }

    with TestClient(app) as client:
        resp = client.put(f"/members/{created_member_item['_id']}", json=payload)

    assert resp.status_code == 200
    assert resp.json() == created_member_item
    fake_instance.update.assert_awaited()


def test_update_404_when_not_found(patch_model):
    fake_instance = FakeMemberModel()
    fake_instance.get_by_id.return_value = None

    patch_model(fake_instance)

    payload = {"first_name": "A", "last_name": "B", "middle_name": "C", "address": "D"}

    with TestClient(app) as client:
        resp = client.put("/members/68df53d345febe98a9137288", json=payload)

    assert resp.status_code == 404


def test_delete_returns_204(patch_model, created_member_item):
    fake_instance = FakeMemberModel()
    fake_instance.get_by_id.return_value = created_member_item
    fake_instance.delete.return_value = None

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.delete(f"/members/{created_member_item['_id']}")

    assert resp.status_code == 204
    fake_instance.delete.assert_awaited()


def test_delete_404_when_not_found(patch_model):
    fake_instance = FakeMemberModel()
    fake_instance.get_by_id.return_value = None

    patch_model(fake_instance)

    with TestClient(app) as client:
        resp = client.delete("/members/68df53d345febe98a9137288")

    assert resp.status_code == 404
