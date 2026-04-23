"""REST API tests for /api/todos."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path):
    return Settings(
        vault_path=str(tmp_path / "vault"),
        data_path=str(tmp_path / "data"),
        auth_password="test-pass",
        llm_provider="openai",
        llm_api_key="sk-test",
        llm_model="gpt-4o",
        scheduler_autostart=False,
    )


@pytest.fixture
def client(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def authed_client(client):
    assert client.post("/api/auth/login", json={"password": "test-pass"}).status_code == 200
    return client


def test_todos_requires_auth(client):
    assert client.get("/api/todos").status_code == 401


def test_list_empty(authed_client):
    # Fresh vault has todos.md with just "# Todos\n", no actual todos.
    r = authed_client.get("/api/todos")
    assert r.status_code == 200
    assert r.json() == []


def test_create_and_list(authed_client):
    r = authed_client.post(
        "/api/todos",
        json={"text": "Call Volvo", "due": "2026-04-25", "priority": "high"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["text"] == "Call Volvo"
    assert body["due"] == "2026-04-25"
    assert body["priority"] == "high"
    assert body["done"] is False

    r = authed_client.get("/api/todos")
    listing = r.json()
    assert len(listing) == 1
    assert listing[0]["text"] == "Call Volvo"


def test_toggle_done(authed_client):
    created = authed_client.post(
        "/api/todos", json={"text": "write tests"}
    ).json()
    r = authed_client.post(f"/api/todos/{created['id']}/toggle")
    assert r.status_code == 200
    assert r.json()["done"] is True
    assert r.json()["completed_at"] is not None

    # Toggle back.
    r2 = authed_client.post(f"/api/todos/{r.json()['id']}/toggle")
    assert r2.json()["done"] is False
    assert r2.json()["completed_at"] is None


def test_update_todo(authed_client):
    created = authed_client.post(
        "/api/todos", json={"text": "old text"}
    ).json()
    r = authed_client.patch(
        f"/api/todos/{created['id']}",
        json={"text": "new text", "due": "2027-01-01", "priority": "low"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "new text"
    assert body["due"] == "2027-01-01"
    assert body["priority"] == "low"


def test_delete_todo(authed_client):
    created = authed_client.post(
        "/api/todos", json={"text": "remove me"}
    ).json()
    r = authed_client.delete(f"/api/todos/{created['id']}")
    assert r.status_code == 204
    assert authed_client.get("/api/todos").json() == []


def test_unknown_id_is_404(authed_client):
    assert authed_client.post("/api/todos/nope/toggle").status_code == 404
    assert authed_client.patch(
        "/api/todos/nope", json={"text": "x"}
    ).status_code == 404
    assert authed_client.delete("/api/todos/nope").status_code == 404


def test_toggle_preserves_metadata(authed_client):
    created = authed_client.post(
        "/api/todos",
        json={"text": "Task with #tag", "due": "2026-05-01", "priority": "medium"},
    ).json()
    assert created["tags"] == ["tag"]

    toggled = authed_client.post(f"/api/todos/{created['id']}/toggle").json()
    assert toggled["tags"] == ["tag"]
    assert toggled["due"] == "2026-05-01"
    assert toggled["priority"] == "medium"
    assert toggled["done"] is True
