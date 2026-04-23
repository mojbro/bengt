"""Tests for automatic conversation titling after first turn."""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import AuditService, ConversationService
from app.db.models import Base
from app.llm import Message, StreamEvent, TextDelta, ToolSpec, Usage
from app.titling import _clean_title, maybe_auto_title
from app.ws_manager import ConnectionManager


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


class FakeWsManager(ConnectionManager):
    def __init__(self) -> None:
        super().__init__()
        self.broadcasts: list[dict[str, Any]] = []

    async def broadcast(self, data: dict[str, Any]) -> None:
        self.broadcasts.append(data)


@pytest.fixture
def services():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return {
        "conversations": ConversationService(factory),
        "audit": AuditService(factory),
        "ws": FakeWsManager(),
    }


# -------------------- _clean_title


def test_clean_title_strips_quotes():
    assert _clean_title('"Planning the trip"') == "Planning the trip"
    assert _clean_title("'Planning the trip'") == "Planning the trip"


def test_clean_title_drops_trailing_period():
    assert _clean_title("About the project.") == "About the project"


def test_clean_title_takes_first_line_only():
    assert _clean_title("One-line title\nsome extra") == "One-line title"


def test_clean_title_caps_length():
    out = _clean_title("x" * 200)
    assert len(out) <= 80


# -------------------- maybe_auto_title


async def test_auto_title_skips_if_already_renamed(services):
    conv = services["conversations"].create(title="My custom name")
    services["conversations"].append_message(conv.id, "user", "hi")
    services["conversations"].append_message(conv.id, "assistant", "hello")

    provider = ScriptedProvider([[TextDelta("Planning trip"), Usage(10, 3, None)]])
    await maybe_auto_title(
        conv.id,
        services["conversations"],
        provider,
        services["audit"],
        services["ws"],
    )
    # Should not have called the LLM.
    assert provider.call_count == 0
    # Title unchanged.
    assert services["conversations"].get(conv.id).title == "My custom name"


async def test_auto_title_skips_without_assistant_message(services):
    conv = services["conversations"].create(title="New thread")
    services["conversations"].append_message(conv.id, "user", "hi")
    # No assistant message yet.

    provider = ScriptedProvider([[TextDelta("x"), Usage(1, 1, None)]])
    await maybe_auto_title(
        conv.id,
        services["conversations"],
        provider,
        services["audit"],
        services["ws"],
    )
    assert provider.call_count == 0
    assert services["conversations"].get(conv.id).title == "New thread"


async def test_auto_title_sets_title_and_broadcasts(services):
    conv = services["conversations"].create(title="New thread")
    services["conversations"].append_message(conv.id, "user", "planning a hiking trip")
    services["conversations"].append_message(
        conv.id, "assistant", "Great — where are you thinking of going?"
    )

    provider = ScriptedProvider([[TextDelta("Hiking trip plans"), Usage(40, 3, 0.0001)]])
    await maybe_auto_title(
        conv.id,
        services["conversations"],
        provider,
        services["audit"],
        services["ws"],
    )
    assert services["conversations"].get(conv.id).title == "Hiking trip plans"
    # One broadcast, shape includes the new title.
    assert len(services["ws"].broadcasts) == 1
    payload = services["ws"].broadcasts[0]
    assert payload["type"] == "notification"
    assert payload["kind"] == "conversation_renamed"
    assert payload["conversation_id"] == conv.id
    assert payload["title"] == "Hiking trip plans"


async def test_auto_title_records_llm_call_in_audit(services):
    conv = services["conversations"].create(title="New thread")
    services["conversations"].append_message(conv.id, "user", "hi")
    services["conversations"].append_message(conv.id, "assistant", "yo")

    provider = ScriptedProvider([[TextDelta("Quick hello"), Usage(12, 2, 0.001)]])
    await maybe_auto_title(
        conv.id,
        services["conversations"],
        provider,
        services["audit"],
        services["ws"],
    )
    entries = services["audit"].recent()
    assert len(entries) == 1
    assert entries[0].kind == "llm_call"
    assert entries[0].conversation_id == conv.id
    assert entries[0].cost_usd == pytest.approx(0.001)


async def test_auto_title_ignores_llm_failure(services):
    conv = services["conversations"].create(title="New thread")
    services["conversations"].append_message(conv.id, "user", "hi")
    services["conversations"].append_message(conv.id, "assistant", "yo")

    class BoomProvider:
        name = "boom"
        model = "boom"

        async def stream(self, messages, tools=None):
            raise RuntimeError("provider down")
            yield  # pragma: no cover

    await maybe_auto_title(
        conv.id,
        services["conversations"],
        BoomProvider(),
        services["audit"],
        services["ws"],
    )
    # Title unchanged, nothing broadcast.
    assert services["conversations"].get(conv.id).title == "New thread"
    assert services["ws"].broadcasts == []


async def test_auto_title_ignores_empty_response(services):
    conv = services["conversations"].create(title="New thread")
    services["conversations"].append_message(conv.id, "user", "hi")
    services["conversations"].append_message(conv.id, "assistant", "yo")

    provider = ScriptedProvider([[Usage(10, 0, None)]])  # no text at all
    await maybe_auto_title(
        conv.id,
        services["conversations"],
        provider,
        services["audit"],
        services["ws"],
    )
    assert services["conversations"].get(conv.id).title == "New thread"
    assert services["ws"].broadcasts == []
