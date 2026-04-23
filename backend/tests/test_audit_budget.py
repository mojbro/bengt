"""Audit log + budget enforcement tests.

Covers the DB layer (record + query + daily sum), BudgetService arithmetic,
and AgentLoop integration (records on Usage events + tool results, refuses
to start a new iteration when the cap is spent).
"""

from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent import AgentError, AgentLoop, AgentToolResult, AgentUsage, Tool, ToolRegistry
from app.budget import BudgetService
from app.db import AuditService
from app.db.models import AuditEntry, Base
from app.llm import Message, StreamEvent, TextDelta, ToolCall, ToolCallEvent, ToolSpec, Usage
from app.vault import VaultService


@pytest.fixture
def audit_service():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return AuditService(factory)


@pytest.fixture
def vault(tmp_path):
    v = VaultService(tmp_path / "vault")
    v.bootstrap()
    return v


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


# -------------------- AuditService


def test_record_llm_call_sets_cost(audit_service):
    e = audit_service.record_llm_call(
        provider="openai",
        model="gpt-4o",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.001,
    )
    assert e.kind == "llm_call"
    assert e.cost_usd == pytest.approx(0.001)
    assert e.data["model"] == "gpt-4o"
    assert e.data["input_tokens"] == 100


def test_record_llm_call_with_unknown_cost_stores_zero(audit_service):
    e = audit_service.record_llm_call(
        provider="openai",
        model="gpt-9999",
        input_tokens=10,
        output_tokens=5,
        cost_usd=None,
    )
    assert e.cost_usd == 0.0


def test_record_tool_invocation_truncates_long_args(audit_service):
    long = "x" * 500
    e = audit_service.record_tool_invocation(
        name="write_file",
        arguments={"path": "a.md", "content": long},
        result="wrote a.md",
        error=False,
    )
    assert e.kind == "tool_invocation"
    assert e.cost_usd == 0.0
    assert e.data["name"] == "write_file"
    assert len(e.data["arguments"]["content"]) < 500
    assert "chars" in e.data["arguments"]["content"]


def test_recent_orders_newest_first(audit_service):
    audit_service.record_llm_call(
        provider="openai", model="a", input_tokens=1, output_tokens=1, cost_usd=0.001
    )
    audit_service.record_tool_invocation(
        name="x", arguments={}, result="y", error=False
    )
    entries = audit_service.recent()
    assert len(entries) == 2
    # Second record is newer, should be first.
    assert entries[0].kind == "tool_invocation"


def test_cost_today_sums_only_today(audit_service):
    audit_service.record_llm_call(
        provider="openai", model="a", input_tokens=1, output_tokens=1, cost_usd=0.01
    )
    audit_service.record_llm_call(
        provider="openai", model="a", input_tokens=1, output_tokens=1, cost_usd=0.02
    )
    assert audit_service.cost_today_utc() == pytest.approx(0.03)

    # Backdate an entry to yesterday — should not count in today's total.
    with audit_service._factory() as session:
        yesterday = datetime.now(timezone.utc) - timedelta(days=2)
        session.add(
            AuditEntry(
                id="yesterday-1",
                timestamp=yesterday,
                kind="llm_call",
                cost_usd=100.0,
                data={},
            )
        )
        session.commit()
    assert audit_service.cost_today_utc() == pytest.approx(0.03)


# -------------------- BudgetService


def test_budget_status_reflects_spend(audit_service):
    budget = BudgetService(audit_service, cap_usd=5.0)
    assert budget.status().spent_usd == 0.0
    assert budget.status().exceeded is False

    audit_service.record_llm_call(
        provider="openai", model="a", input_tokens=1, output_tokens=1, cost_usd=3.0
    )
    status = budget.status()
    assert status.spent_usd == pytest.approx(3.0)
    assert status.remaining_usd == pytest.approx(2.0)
    assert status.exceeded is False


def test_budget_exceeded_when_cap_hit(audit_service):
    budget = BudgetService(audit_service, cap_usd=1.0)
    audit_service.record_llm_call(
        provider="openai", model="a", input_tokens=1, output_tokens=1, cost_usd=1.5
    )
    assert budget.exceeded() is True
    assert budget.status().remaining_usd == 0.0


# -------------------- AgentLoop integration


async def test_agent_records_llm_call(audit_service, vault):
    provider = ScriptedProvider([
        [TextDelta("hi"), Usage(100, 50, 0.0015)],
    ])
    agent = AgentLoop(
        llm=provider, tools=ToolRegistry(), vault=vault, audit=audit_service
    )
    events = [e async for e in agent.run("hello", conversation_id="conv-123")]
    usage_events = [e for e in events if isinstance(e, AgentUsage)]
    assert len(usage_events) == 1

    recent = audit_service.recent()
    llm_entries = [e for e in recent if e.kind == "llm_call"]
    assert len(llm_entries) == 1
    entry = llm_entries[0]
    assert entry.conversation_id == "conv-123"
    assert entry.cost_usd == pytest.approx(0.0015)
    assert entry.data["input_tokens"] == 100


async def test_agent_records_tool_invocation(audit_service, vault):
    registry = ToolRegistry()

    async def echo(args: dict[str, Any]) -> str:
        return args["m"]

    registry.register(
        Tool(
            name="echo",
            description="echo",
            parameters={"type": "object", "properties": {"m": {"type": "string"}}},
            fn=echo,
        )
    )

    provider = ScriptedProvider([
        [
            ToolCallEvent(ToolCall(id="c1", name="echo", arguments={"m": "hi"})),
            Usage(5, 1, None),
        ],
        [TextDelta("done"), Usage(10, 2, None)],
    ])
    agent = AgentLoop(
        llm=provider, tools=registry, vault=vault, audit=audit_service
    )
    events = [e async for e in agent.run("use echo")]
    assert any(isinstance(e, AgentToolResult) for e in events)

    tool_entries = [
        e for e in audit_service.recent() if e.kind == "tool_invocation"
    ]
    assert len(tool_entries) == 1
    assert tool_entries[0].data["name"] == "echo"
    assert tool_entries[0].data["error"] is False


async def test_agent_records_tool_error(audit_service, vault):
    registry = ToolRegistry()

    async def boom(args: dict[str, Any]) -> str:
        raise RuntimeError("nope")

    registry.register(
        Tool(name="boom", description="", parameters={"type": "object"}, fn=boom)
    )

    provider = ScriptedProvider([
        [ToolCallEvent(ToolCall(id="c1", name="boom", arguments={})), Usage(5, 1, None)],
        [TextDelta("sorry"), Usage(5, 1, None)],
    ])
    agent = AgentLoop(
        llm=provider, tools=registry, vault=vault, audit=audit_service
    )
    [e async for e in agent.run("boom")]

    tool_entries = [
        e for e in audit_service.recent() if e.kind == "tool_invocation"
    ]
    assert len(tool_entries) == 1
    assert tool_entries[0].data["error"] is True
    assert "nope" in tool_entries[0].data["result_preview"]


async def test_agent_refuses_when_budget_exceeded(audit_service, vault):
    # Pre-spend the budget.
    audit_service.record_llm_call(
        provider="openai",
        model="gpt-4o",
        input_tokens=100_000,
        output_tokens=100_000,
        cost_usd=5.0,
    )
    budget = BudgetService(audit_service, cap_usd=5.0)

    provider = ScriptedProvider([[TextDelta("this should never run"), Usage(0, 0, None)]])
    agent = AgentLoop(
        llm=provider,
        tools=ToolRegistry(),
        vault=vault,
        audit=audit_service,
        budget=budget,
    )
    events = [e async for e in agent.run("hi")]
    errors = [e for e in events if isinstance(e, AgentError)]
    assert len(errors) == 1
    assert "budget" in errors[0].message.lower()
    assert provider.call_count == 0, "LLM was called despite budget exhaustion"


async def test_agent_runs_when_budget_not_exceeded(audit_service, vault):
    audit_service.record_llm_call(
        provider="openai",
        model="gpt-4o",
        input_tokens=1,
        output_tokens=1,
        cost_usd=1.0,
    )
    budget = BudgetService(audit_service, cap_usd=5.0)

    provider = ScriptedProvider([[TextDelta("still here"), Usage(1, 1, 0.001)]])
    agent = AgentLoop(
        llm=provider,
        tools=ToolRegistry(),
        vault=vault,
        audit=audit_service,
        budget=budget,
    )
    events = [e async for e in agent.run("hi")]
    assert provider.call_count == 1
    assert not any(isinstance(e, AgentError) for e in events)
