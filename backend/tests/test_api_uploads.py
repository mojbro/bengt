"""REST tests for /api/uploads.

The summary LLM call is stubbed so tests are fast and don't eat tokens.
"""

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm import Message, StreamEvent, TextDelta, ToolSpec, Usage
from app.main import create_app


class StubLLM:
    name = "mock"
    model = "mock-model"

    def __init__(self, reply: str = '{"summary": "stub summary", "tags": ["alpha", "beta"]}'):
        self.reply = reply

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        yield TextDelta(self.reply)
        yield Usage(10, 5, None)


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
        # Swap in a stub LLM so upload doesn't hit OpenAI.
        client.app.state.llm = StubLLM()
        yield client


@pytest.fixture
def authed_client(client):
    assert client.post("/api/auth/login", json={"password": "test-pass"}).status_code == 200
    return client


def test_uploads_requires_auth(client):
    r = client.post(
        "/api/uploads",
        files={"file": ("x.txt", b"hi", "text/plain")},
    )
    assert r.status_code == 401


def test_upload_plain_text_writes_md_with_frontmatter(authed_client, tmp_path):
    r = authed_client.post(
        "/api/uploads",
        files={"file": ("meeting-notes.txt", b"key point one\n\nkey point two", "text/plain")},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["md_path"].startswith("uploads/") and body["md_path"].endswith(".md")
    assert body["original_path"].endswith("meeting-notes.txt")
    assert body["summary"] == "stub summary"
    assert body["tags"] == ["alpha", "beta"]
    assert body["extracted_chars"] > 0

    # Fetch the .md content and check frontmatter + body.
    md = authed_client.get(
        "/api/vault/file", params={"path": body["md_path"]}
    ).json()
    assert "source: meeting-notes.txt" in md["content"]
    assert "tags: [alpha, beta]" in md["content"]
    assert "key point one" in md["content"]
    assert 'summary: "stub summary"' in md["content"]


def test_upload_rejects_unsupported_type(authed_client):
    r = authed_client.post(
        "/api/uploads",
        files={"file": ("photo.jpg", b"\xff\xd8\xff\xe0binary", "image/jpeg")},
    )
    assert r.status_code == 415
    assert "pdf" in r.json()["detail"].lower()


def test_upload_rejects_empty_body(authed_client):
    r = authed_client.post(
        "/api/uploads",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert r.status_code == 400


def test_upload_extracted_indexed(authed_client):
    """After upload, the .md should be searchable via ChromaDB index."""
    authed_client.post(
        "/api/uploads",
        files={
            "file": (
                "volvo-brief.md",
                b"# Volvo brief\n\nSupplier contract renewal for Q2.",
                "text/markdown",
            ),
        },
    )
    # Query the indexer directly via app state — the .md should be indexed
    # by the VaultService write hook.
    indexer = authed_client.app.state.indexer
    hits = indexer.search("supplier contract renewal", limit=5)
    assert any("volvo-brief" in h.path for h in hits)


def test_download_streams_original(authed_client):
    created = authed_client.post(
        "/api/uploads",
        files={"file": ("draft.txt", b"hello world", "text/plain")},
    ).json()
    r = authed_client.get(
        "/api/uploads/download",
        params={"path": created["original_path"]},
    )
    assert r.status_code == 200
    assert r.content == b"hello world"
    assert "attachment" in r.headers.get("content-disposition", "")


def test_download_rejects_traversal(authed_client):
    r = authed_client.get(
        "/api/uploads/download",
        params={"path": "../../etc/passwd"},
    )
    assert r.status_code == 400


def test_download_404_for_missing(authed_client):
    r = authed_client.get(
        "/api/uploads/download",
        params={"path": "uploads/2099-01-01/ghost.pdf"},
    )
    assert r.status_code == 404
