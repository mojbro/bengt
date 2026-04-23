"""Unit tests for the scheduled-job fire callable. Uses a ScriptedProvider
so we don't hit OpenAI; exercises the persistence + broadcast path.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent import AgentLoop, ToolRegistry
from app.db import ConversationService
from app.db.models import Base
from app.llm import Message, StreamEvent, TextDelta, ToolSpec, Usage
from app.scheduler_runner import (
    SchedulerServices,
    clear_services,
    fire_scheduled_job,
    register_services,
)
from app.vault import VaultService


class FakeWsManager:
    def __init__(self) -> None:
        self.broadcasts: list[dict[str, Any]] = []

    async def broadcast(self, data: dict[str, Any]) -> None:
        self.broadcasts.append(data)


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
def conv_service():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return ConversationService(factory)


@pytest.fixture
def vault(tmp_path):
    v = VaultService(tmp_path / "vault")
    v.bootstrap()
    return v


@pytest.fixture(autouse=True)
def reset_services():
    yield
    clear_services()


async def test_fire_without_services_registered_is_noop():
    # Nothing registered yet — should not raise.
    await fire_scheduled_job("anything")


async def test_fire_runs_agent_and_persists(conv_service, vault):
    conv = conv_service.create(title="Scheduled")

    provider = ScriptedProvider([
        [TextDelta("Reminder noted."), Usage(10, 5, None)],
    ])
    agent = AgentLoop(llm=provider, tools=ToolRegistry(), vault=vault)
    ws = FakeWsManager()

    register_services(
        SchedulerServices(
            agent=agent,
            conversations=conv_service,
            ws_manager=ws,
            scheduled_conversation_id=conv.id,
        )
    )

    await fire_scheduled_job("Remind me about the board meeting")

    msgs = conv_service.messages(conv.id)
    roles = [m.role for m in msgs]
    assert roles == ["user", "assistant"]
    assert "scheduled reminder" in msgs[0].content
    assert "board meeting" in msgs[0].content
    assert msgs[1].content == "Reminder noted."


async def test_fire_broadcasts_notification(conv_service, vault):
    conv = conv_service.create(title="Scheduled")

    provider = ScriptedProvider([[TextDelta("hi"), Usage(0, 0, None)]])
    agent = AgentLoop(llm=provider, tools=ToolRegistry(), vault=vault)
    ws = FakeWsManager()

    register_services(
        SchedulerServices(
            agent=agent,
            conversations=conv_service,
            ws_manager=ws,
            scheduled_conversation_id=conv.id,
        )
    )

    await fire_scheduled_job("test instruction")

    assert len(ws.broadcasts) == 1
    payload = ws.broadcasts[0]
    assert payload["type"] == "notification"
    assert payload["kind"] == "scheduled_fired"
    assert payload["conversation_id"] == conv.id
    assert payload["instruction"] == "test instruction"


async def test_fire_surfaces_agent_errors(conv_service, vault):
    conv = conv_service.create(title="Scheduled")

    class BoomProvider:
        name = "boom"
        model = "boom"

        async def stream(self, messages, tools=None):
            raise RuntimeError("llm unavailable")
            yield  # pragma: no cover - makes it a generator

    agent = AgentLoop(llm=BoomProvider(), tools=ToolRegistry(), vault=vault)
    ws = FakeWsManager()

    register_services(
        SchedulerServices(
            agent=agent,
            conversations=conv_service,
            ws_manager=ws,
            scheduled_conversation_id=conv.id,
        )
    )

    # Should not raise — errors become an assistant message.
    await fire_scheduled_job("will fail")

    msgs = conv_service.messages(conv.id)
    roles = [m.role for m in msgs]
    assert roles == ["user", "assistant"]
    assert "failed" in msgs[1].content.lower()

    # Still broadcasts so the UI gets a poke.
    assert len(ws.broadcasts) == 1
