"""Real-API integration test for the agent loop with mock tools.

Skipped by default. Run with:

    docker compose exec backend pytest -m integration -v
"""

import pytest

from app.agent import (
    AgentLoop,
    AgentText,
    AgentToolResult,
    AgentToolStart,
    ToolRegistry,
    register_mock_tools,
)
from app.agent.vault_tools import register_vault_tools
from app.config import Settings
from app.indexer import Indexer
from app.llm import build_provider
from app.vault import VaultService

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not Settings().llm_api_key,
        reason="LLM_API_KEY is empty — integration tests need a real key",
    ),
]


async def test_agent_uses_add_tool_end_to_end(vault: VaultService):
    settings = Settings()
    llm = build_provider(settings)
    tools = ToolRegistry()
    register_mock_tools(tools)
    agent = AgentLoop(llm=llm, tools=tools, vault=vault)

    events = []
    async for event in agent.run(
        "What is 7 plus 8? Use the `add` tool to compute it, "
        "then tell me the result in a short sentence."
    ):
        events.append(event)

    starts = [e for e in events if isinstance(e, AgentToolStart)]
    assert any(e.name == "add" for e in starts), (
        f"expected the model to call `add`; got: {starts!r}"
    )

    results = [e for e in events if isinstance(e, AgentToolResult)]
    assert any(r.result == "15" and not r.error for r in results), (
        f"expected `add` to return 15; got: {results!r}"
    )

    text = "".join(e.text for e in events if isinstance(e, AgentText))
    assert "15" in text, f"expected '15' in final text; got: {text!r}"


async def test_agent_answers_from_vault(tmp_path):
    """End-to-end: seed a note, ask about it, verify agent retrieves and answers."""
    indexer = Indexer(db_path=tmp_path / "chroma")
    vault = VaultService(tmp_path / "vault", indexer=indexer)
    vault.bootstrap()
    vault.write(
        "notes/volvo.md",
        "Meeting with Volvo on Friday at 10:00 about the contract renewal.",
        actor="user",
    )

    llm = build_provider(Settings())
    tools = ToolRegistry()
    register_vault_tools(tools, vault, indexer)
    agent = AgentLoop(llm=llm, tools=tools, vault=vault)

    events = []
    async for event in agent.run(
        "When is my Volvo meeting? Use the vault to find out."
    ):
        events.append(event)

    starts = [e for e in events if isinstance(e, AgentToolStart)]
    used_tools = {s.name for s in starts}
    assert used_tools & {"search_vault", "read_file", "list_vault"}, (
        f"expected the agent to reach into the vault; used: {used_tools}"
    )

    text = "".join(e.text for e in events if isinstance(e, AgentText))
    assert "Friday" in text or "10" in text, (
        f"expected the answer to mention the time/day; got: {text!r}"
    )
