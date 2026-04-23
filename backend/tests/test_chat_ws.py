"""WebSocket chat tests — use a ScriptedProvider so we don't hit OpenAI."""

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.agent import AgentLoop
from app.config import Settings
from app.db import ConversationService
from app.llm import (
    Message,
    StreamEvent,
    TextDelta,
    ToolCall,
    ToolCallEvent,
    ToolSpec,
    Usage,
)
from app.main import create_app


class ScriptedProvider:
    name = "mock"
    model = "mock-model"

    def __init__(self, scripts: list[list[StreamEvent]]):
        self._scripts = scripts
        self.call_count = 0

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        script = self._scripts[self.call_count]
        self.call_count += 1
        for event in script:
            yield event


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


def _swap_agent(client, scripts):
    provider = ScriptedProvider(scripts)
    app = client.app
    agent = AgentLoop(llm=provider, tools=app.state.tools, vault=app.state.vault)
    app.state.agent = agent
    return provider


def _create_conversation(client) -> str:
    r = client.post("/api/conversations", json={"title": "test"})
    assert r.status_code == 201
    return r.json()["id"]


def test_ws_requires_auth(client):
    with pytest.raises(Exception):
        # starlette's TestClient raises on 1008 close during handshake
        with client.websocket_connect("/api/chat/ws"):
            pass


def test_ws_simple_text_response(authed_client):
    conv_id = _create_conversation(authed_client)
    _swap_agent(
        authed_client,
        [[TextDelta("Hello"), TextDelta(" world"), Usage(10, 5, 0.001)]],
    )
    with authed_client.websocket_connect("/api/chat/ws") as ws:
        ws.send_json({"conversation_id": conv_id, "content": "hi"})
        events = []
        while True:
            event = ws.receive_json()
            events.append(event)
            if event["type"] == "done":
                break

    types = [e["type"] for e in events]
    assert types.count("text") == 2
    assert "usage" in types and "done" in types

    text = "".join(e["text"] for e in events if e["type"] == "text")
    assert text == "Hello world"

    # Persistence: conversation should now have user + assistant messages
    detail = authed_client.get(f"/api/conversations/{conv_id}").json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]
    assert detail["messages"][0]["content"] == "hi"
    assert detail["messages"][1]["content"] == "Hello world"


def test_ws_tool_roundtrip_persists(authed_client):
    conv_id = _create_conversation(authed_client)
    # LLM: iteration 1 → calls echo tool; iteration 2 → text response
    # But our real tools registry doesn't have `echo`. Let's use one that
    # IS registered by register_vault_tools — `list_vault` with empty path.
    tc = ToolCall(id="c1", name="list_vault", arguments={"path": ""})
    _swap_agent(
        authed_client,
        [
            [ToolCallEvent(tc), Usage(5, 3, None)],
            [TextDelta("Done."), Usage(15, 5, None)],
        ],
    )
    with authed_client.websocket_connect("/api/chat/ws") as ws:
        ws.send_json({"conversation_id": conv_id, "content": "look around"})
        events = []
        while True:
            event = ws.receive_json()
            events.append(event)
            if event["type"] == "done":
                break

    types = [e["type"] for e in events]
    assert "tool_start" in types
    assert "tool_result" in types
    assert "done" in types

    # DB rows: user → assistant(with tool_calls) → tool → assistant(text)
    detail = authed_client.get(f"/api/conversations/{conv_id}").json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant", "tool", "assistant"]
    assistant_with_tools = detail["messages"][1]
    assert assistant_with_tools["tool_calls"]
    assert assistant_with_tools["tool_calls"][0]["name"] == "list_vault"
    tool_row = detail["messages"][2]
    assert tool_row["tool_call_id"] == "c1"
    final = detail["messages"][3]
    assert final["content"] == "Done."


def test_ws_unknown_conversation_reports_error(authed_client):
    _swap_agent(authed_client, [[TextDelta("x"), Usage(0, 0, None)]])
    with authed_client.websocket_connect("/api/chat/ws") as ws:
        ws.send_json({"conversation_id": "does-not-exist", "content": "hi"})
        event = ws.receive_json()
        assert event["type"] == "error"
        assert "not found" in event["message"]


def test_ws_bad_payload_reports_error(authed_client):
    with authed_client.websocket_connect("/api/chat/ws") as ws:
        ws.send_json({"missing": "fields"})
        event = ws.receive_json()
        assert event["type"] == "error"


def test_ws_ignores_ping_frames(authed_client):
    """Pings keep the connection alive but shouldn't surface errors."""
    conv_id = _create_conversation(authed_client)
    _swap_agent(
        authed_client,
        [[TextDelta("pong"), Usage(0, 0, None)]],
    )
    with authed_client.websocket_connect("/api/chat/ws") as ws:
        ws.send_json({"type": "ping"})
        ws.send_json({"type": "ping"})
        # After pings, a real message should still work normally.
        ws.send_json({"conversation_id": conv_id, "content": "hello"})
        events = []
        while True:
            ev = ws.receive_json()
            events.append(ev)
            if ev["type"] == "done":
                break
    assert all(e["type"] != "error" for e in events)


def test_ws_history_is_threaded(authed_client):
    conv_id = _create_conversation(authed_client)
    provider = _swap_agent(
        authed_client,
        [
            [TextDelta("first"), Usage(0, 0, None)],
            [TextDelta("second"), Usage(0, 0, None)],
        ],
    )
    with authed_client.websocket_connect("/api/chat/ws") as ws:
        ws.send_json({"conversation_id": conv_id, "content": "hi"})
        while ws.receive_json()["type"] != "done":
            pass
        ws.send_json({"conversation_id": conv_id, "content": "again"})
        while ws.receive_json()["type"] != "done":
            pass

    # Both turns happened, and DB has 4 messages (user, assistant, user, assistant)
    detail = authed_client.get(f"/api/conversations/{conv_id}").json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert provider.call_count == 2
