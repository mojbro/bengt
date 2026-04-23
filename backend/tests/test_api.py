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
        auto_title=False,
    )


@pytest.fixture
def client(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def authed_client(client):
    r = client.post("/api/auth/login", json={"password": "test-pass"})
    assert r.status_code == 200
    return client


# -------------------- health


def test_health_open(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# -------------------- auth


def test_login_wrong_password_is_rejected(client):
    r = client.post("/api/auth/login", json={"password": "WRONG"})
    assert r.status_code == 401


def test_login_right_password_authenticates(client):
    r = client.post("/api/auth/login", json={"password": "test-pass"})
    assert r.status_code == 200
    assert r.json() == {"authed": True}

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == {"authed": True}


def test_logout_clears_session(authed_client):
    r = authed_client.post("/api/auth/logout")
    assert r.status_code == 200
    assert r.json() == {"authed": False}
    me = authed_client.get("/api/auth/me")
    assert me.json() == {"authed": False}


def test_me_when_not_authed(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json() == {"authed": False}


# -------------------- auth gate


def test_vault_requires_auth(client):
    assert client.get("/api/vault/tree").status_code == 401
    assert client.get("/api/vault/file?path=todos.md").status_code == 401


def test_conversations_requires_auth(client):
    assert client.get("/api/conversations").status_code == 401
    assert client.post("/api/conversations", json={"title": "x"}).status_code == 401


# -------------------- vault


def test_vault_tree_lists_stub_files(authed_client):
    r = authed_client.get("/api/vault/tree")
    assert r.status_code == 200
    paths = {entry["path"] for entry in r.json()}
    assert {"todos.md", "memory.md", "preferences.md"}.issubset(paths)


def test_vault_read_file(authed_client):
    r = authed_client.get("/api/vault/file", params={"path": "todos.md"})
    assert r.status_code == 200
    body = r.json()
    assert body["path"] == "todos.md"
    assert body["content"].startswith("# Todos")


def test_vault_read_missing_is_404(authed_client):
    r = authed_client.get("/api/vault/file", params={"path": "does-not-exist.md"})
    assert r.status_code == 404


def test_vault_write_then_read_roundtrip(authed_client):
    path = "notes/via-api.md"
    r = authed_client.put(
        "/api/vault/file",
        params={"path": path},
        json={"content": "hello from API"},
    )
    assert r.status_code == 200
    read = authed_client.get("/api/vault/file", params={"path": path})
    assert read.status_code == 200
    assert read.json()["content"] == "hello from API"


def test_vault_write_rejects_traversal(authed_client):
    r = authed_client.put(
        "/api/vault/file",
        params={"path": "../escape.md"},
        json={"content": "x"},
    )
    assert r.status_code == 400


def test_vault_read_returns_mtime(authed_client):
    r = authed_client.get("/api/vault/file", params={"path": "todos.md"})
    assert r.status_code == 200
    assert "modified_at" in r.json()


def test_vault_delete_removes_file(authed_client):
    authed_client.put(
        "/api/vault/file",
        params={"path": "notes/to-delete.md"},
        json={"content": "bye"},
    )
    assert authed_client.get(
        "/api/vault/file", params={"path": "notes/to-delete.md"}
    ).status_code == 200

    r = authed_client.delete("/api/vault/file", params={"path": "notes/to-delete.md"})
    assert r.status_code == 204

    # File is now gone.
    assert authed_client.get(
        "/api/vault/file", params={"path": "notes/to-delete.md"}
    ).status_code == 404


def test_vault_delete_missing_is_404(authed_client):
    r = authed_client.delete("/api/vault/file", params={"path": "nope.md"})
    assert r.status_code == 404


def test_vault_delete_rejects_traversal(authed_client):
    r = authed_client.delete("/api/vault/file", params={"path": "../escape.md"})
    assert r.status_code == 400


def test_vault_write_conflict_when_file_changed(authed_client):
    import time

    authed_client.put(
        "/api/vault/file",
        params={"path": "notes/conflict.md"},
        json={"content": "original"},
    )
    first = authed_client.get(
        "/api/vault/file", params={"path": "notes/conflict.md"}
    ).json()

    time.sleep(1.1)  # push mtime past the 0.5s epsilon
    authed_client.put(
        "/api/vault/file",
        params={"path": "notes/conflict.md"},
        json={"content": "agent wrote this"},
    )

    conflict = authed_client.put(
        "/api/vault/file",
        params={"path": "notes/conflict.md"},
        json={
            "content": "user overwrite attempt",
            "expected_modified_at": first["modified_at"],
        },
    )
    assert conflict.status_code == 409
    after = authed_client.get(
        "/api/vault/file", params={"path": "notes/conflict.md"}
    ).json()
    assert after["content"] == "agent wrote this"


def test_vault_write_succeeds_with_fresh_mtime(authed_client):
    authed_client.put(
        "/api/vault/file",
        params={"path": "notes/fresh.md"},
        json={"content": "hello"},
    )
    current = authed_client.get(
        "/api/vault/file", params={"path": "notes/fresh.md"}
    ).json()
    r = authed_client.put(
        "/api/vault/file",
        params={"path": "notes/fresh.md"},
        json={
            "content": "hello v2",
            "expected_modified_at": current["modified_at"],
        },
    )
    assert r.status_code == 200


# -------------------- conversations


def test_conversations_list_empty(authed_client):
    r = authed_client.get("/api/conversations")
    assert r.status_code == 200
    assert r.json() == []


def test_conversations_create(authed_client):
    r = authed_client.post("/api/conversations", json={"title": "Planning"})
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Planning"
    assert body["id"]


def test_conversations_get_with_no_messages(authed_client):
    created = authed_client.post(
        "/api/conversations", json={"title": "x"}
    ).json()
    r = authed_client.get(f"/api/conversations/{created['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "x"
    assert body["messages"] == []


def test_conversations_get_unknown_is_404(authed_client):
    r = authed_client.get("/api/conversations/does-not-exist")
    assert r.status_code == 404


def test_conversations_rename(authed_client):
    created = authed_client.post(
        "/api/conversations", json={"title": "old"}
    ).json()
    r = authed_client.patch(
        f"/api/conversations/{created['id']}", json={"title": "new"}
    )
    assert r.status_code == 200
    assert r.json()["title"] == "new"


def test_conversations_delete(authed_client):
    created = authed_client.post(
        "/api/conversations", json={"title": "x"}
    ).json()
    r = authed_client.delete(f"/api/conversations/{created['id']}")
    assert r.status_code == 204
    assert authed_client.get(f"/api/conversations/{created['id']}").status_code == 404


def test_conversations_list_orders_recent_first(authed_client):
    import time

    a = authed_client.post("/api/conversations", json={"title": "A"}).json()
    time.sleep(0.001)
    b = authed_client.post("/api/conversations", json={"title": "B"}).json()
    time.sleep(0.001)
    c = authed_client.post("/api/conversations", json={"title": "C"}).json()
    r = authed_client.get("/api/conversations")
    ids = [conv["id"] for conv in r.json()]
    assert ids == [c["id"], b["id"], a["id"]]
