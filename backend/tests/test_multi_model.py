"""Multi-model support: factory parsing, conversation.model, /api/models."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm.factory import LLMConfigError, build_providers
from app.main import create_app


# -------------------- factory


def test_build_providers_single_model_fallback():
    s = Settings(
        llm_provider="openai",
        llm_api_key="sk-test",
        llm_model="gpt-4o",
        llm_models="",
    )
    providers, default = build_providers(s)
    assert set(providers.keys()) == {"gpt-4o"}
    assert default == "gpt-4o"
    assert providers[default].model == "gpt-4o"


def test_build_providers_multi_model_with_explicit_default():
    s = Settings(
        llm_provider="openai",
        llm_api_key="sk-test",
        llm_model="gpt-4o",
        llm_models='{"fast":"gpt-4o-mini","smart":"gpt-5"}',
        llm_default_model="smart",
    )
    providers, default = build_providers(s)
    assert default == "smart"
    assert providers["fast"].model == "gpt-4o-mini"
    assert providers["smart"].model == "gpt-5"


def test_build_providers_multi_model_implicit_default_is_first_key():
    s = Settings(
        llm_provider="openai",
        llm_api_key="sk-test",
        llm_model="gpt-4o",
        llm_models='{"fast":"gpt-4o-mini","smart":"gpt-5"}',
    )
    _, default = build_providers(s)
    assert default == "fast"


def test_build_providers_rejects_unknown_default():
    s = Settings(
        llm_provider="openai",
        llm_api_key="sk-test",
        llm_model="gpt-4o",
        llm_models='{"fast":"gpt-4o-mini"}',
        llm_default_model="nope",
    )
    with pytest.raises(LLMConfigError, match="isn't one of"):
        build_providers(s)


def test_build_providers_rejects_bad_json():
    s = Settings(
        llm_provider="openai",
        llm_api_key="sk-test",
        llm_model="gpt-4o",
        llm_models="not json",
    )
    with pytest.raises(LLMConfigError, match="valid JSON"):
        build_providers(s)


# -------------------- API


@pytest.fixture
def settings(tmp_path):
    return Settings(
        vault_path=str(tmp_path / "vault"),
        data_path=str(tmp_path / "data"),
        auth_password="test-pass",
        llm_provider="openai",
        llm_api_key="sk-test",
        llm_model="gpt-4o",
        llm_models='{"fast":"gpt-4o-mini","smart":"gpt-5"}',
        llm_default_model="fast",
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
    assert client.post("/api/auth/login", json={"password": "test-pass"}).status_code == 200
    return client


def test_models_endpoint_lists_configured(authed_client):
    r = authed_client.get("/api/models")
    assert r.status_code == 200
    body = r.json()
    assert body["default"] == "fast"
    names = [m["name"] for m in body["models"]]
    assert set(names) == {"fast", "smart"}
    by_name = {m["name"]: m["id"] for m in body["models"]}
    assert by_name["fast"] == "gpt-4o-mini"
    assert by_name["smart"] == "gpt-5"


def test_models_endpoint_requires_auth(client):
    assert client.get("/api/models").status_code == 401


def test_conversation_create_with_model(authed_client):
    r = authed_client.post(
        "/api/conversations",
        json={"title": "deep-dive", "model": "smart"},
    )
    assert r.status_code == 201
    assert r.json()["model"] == "smart"


def test_conversation_patch_sets_model(authed_client):
    created = authed_client.post(
        "/api/conversations", json={"title": "t"}
    ).json()
    assert created["model"] is None
    r = authed_client.patch(
        f"/api/conversations/{created['id']}",
        json={"model": "smart"},
    )
    assert r.status_code == 200
    assert r.json()["model"] == "smart"


def test_conversation_patch_clears_model(authed_client):
    created = authed_client.post(
        "/api/conversations", json={"title": "t", "model": "smart"}
    ).json()
    assert created["model"] == "smart"
    r = authed_client.patch(
        f"/api/conversations/{created['id']}",
        json={"model": None},
    )
    assert r.status_code == 200
    assert r.json()["model"] is None


def test_conversation_patch_title_only_leaves_model_alone(authed_client):
    created = authed_client.post(
        "/api/conversations", json={"title": "t", "model": "smart"}
    ).json()
    r = authed_client.patch(
        f"/api/conversations/{created['id']}",
        json={"title": "renamed"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "renamed"
    assert r.json()["model"] == "smart"  # untouched


def test_get_conversation_includes_model(authed_client):
    created = authed_client.post(
        "/api/conversations", json={"title": "t", "model": "smart"}
    ).json()
    r = authed_client.get(f"/api/conversations/{created['id']}")
    assert r.status_code == 200
    assert r.json()["model"] == "smart"
