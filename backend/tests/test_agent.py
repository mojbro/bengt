from collections.abc import AsyncIterator
from typing import Any

import pytest

from app.agent import (
    AgentDone,
    AgentError,
    AgentLoop,
    AgentText,
    AgentToolResult,
    AgentToolStart,
    AgentUsage,
    Tool,
    ToolRegistry,
)
from app.llm import (
    Message,
    StreamEvent,
    TextDelta,
    ToolCall,
    ToolCallEvent,
    ToolSpec,
    Usage,
)
from app.vault import VaultService


class ScriptedProvider:
    """LLMProvider test double — returns one scripted event list per call."""

    name = "mock"
    model = "mock-model"

    def __init__(self, scripts: list[list[StreamEvent]]):
        self._scripts = scripts
        self.call_count = 0
        self.calls: list[list[Message]] = []
        self.tool_calls_seen: list[list[ToolSpec] | None] = []

    async def stream(
        self, messages: list[Message], tools: list[ToolSpec] | None = None
    ) -> AsyncIterator[StreamEvent]:
        self.calls.append(list(messages))
        self.tool_calls_seen.append(tools)
        script = self._scripts[self.call_count]
        self.call_count += 1
        for event in script:
            yield event


async def _collect(agent: AgentLoop, user_msg: str):
    return [event async for event in agent.run(user_msg)]


async def test_simple_text_response(vault: VaultService):
    provider = ScriptedProvider([
        [TextDelta("Hello"), TextDelta(" world"), Usage(10, 5, 0.001)],
    ])
    agent = AgentLoop(llm=provider, tools=ToolRegistry(), vault=vault)

    events = await _collect(agent, "hi")

    text = "".join(e.text for e in events if isinstance(e, AgentText))
    assert text == "Hello world"
    assert any(isinstance(e, AgentDone) for e in events)
    assert any(isinstance(e, AgentUsage) for e in events)
    assert provider.call_count == 1


async def test_tool_call_roundtrip(vault: VaultService):
    registry = ToolRegistry()

    async def echo(args: dict[str, Any]) -> str:
        return args["msg"]

    registry.register(
        Tool(
            name="echo",
            description="echo",
            parameters={
                "type": "object",
                "properties": {"msg": {"type": "string"}},
                "required": ["msg"],
            },
            fn=echo,
        )
    )

    provider = ScriptedProvider([
        [
            ToolCallEvent(ToolCall(id="c1", name="echo", arguments={"msg": "pong"})),
            Usage(5, 3, 0.0005),
        ],
        [TextDelta("Got pong"), Usage(15, 5, 0.0015)],
    ])
    agent = AgentLoop(llm=provider, tools=registry, vault=vault)

    events = await _collect(agent, "echo pong")

    starts = [e for e in events if isinstance(e, AgentToolStart)]
    assert len(starts) == 1
    assert starts[0].name == "echo"
    assert starts[0].arguments == {"msg": "pong"}

    results = [e for e in events if isinstance(e, AgentToolResult)]
    assert len(results) == 1 and results[0].result == "pong" and not results[0].error

    text = "".join(e.text for e in events if isinstance(e, AgentText))
    assert text == "Got pong"

    # Second call should include the tool result in messages
    second_call = provider.calls[1]
    tool_msgs = [m for m in second_call if m.role == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].content == "pong"
    assert tool_msgs[0].tool_call_id == "c1"


async def test_tool_error_is_surfaced_to_llm(vault: VaultService):
    registry = ToolRegistry()

    async def boom(args: dict[str, Any]) -> str:
        raise RuntimeError("nope")

    registry.register(
        Tool(name="boom", description="", parameters={"type": "object"}, fn=boom)
    )

    provider = ScriptedProvider([
        [ToolCallEvent(ToolCall(id="c1", name="boom", arguments={})), Usage(5, 2, None)],
        [TextDelta("That failed."), Usage(10, 3, None)],
    ])
    agent = AgentLoop(llm=provider, tools=registry, vault=vault)

    events = await _collect(agent, "try boom")

    results = [e for e in events if isinstance(e, AgentToolResult)]
    assert len(results) == 1
    assert results[0].error
    assert "nope" in results[0].result

    # Error text should have been fed back to the LLM in the second call.
    tool_msgs = [m for m in provider.calls[1] if m.role == "tool"]
    assert len(tool_msgs) == 1 and "nope" in tool_msgs[0].content


async def test_unknown_tool_is_reported_as_error(vault: VaultService):
    provider = ScriptedProvider([
        [ToolCallEvent(ToolCall(id="c1", name="ghost", arguments={})), Usage(5, 2, None)],
        [TextDelta("Sorry."), Usage(8, 2, None)],
    ])
    agent = AgentLoop(llm=provider, tools=ToolRegistry(), vault=vault)

    events = await _collect(agent, "anything")

    results = [e for e in events if isinstance(e, AgentToolResult)]
    assert len(results) == 1 and results[0].error
    assert "ghost" in results[0].result


async def test_max_iterations_safety(vault: VaultService):
    registry = ToolRegistry()

    async def keep_going(args: dict[str, Any]) -> str:
        return "again"

    registry.register(
        Tool(
            name="loop",
            description="",
            parameters={"type": "object"},
            fn=keep_going,
        )
    )

    endless = [
        ToolCallEvent(ToolCall(id="c", name="loop", arguments={})),
        Usage(1, 1, None),
    ]
    provider = ScriptedProvider([endless] * 10)
    agent = AgentLoop(llm=provider, tools=registry, vault=vault, max_iterations=3)

    events = await _collect(agent, "stuck")

    errors = [e for e in events if isinstance(e, AgentError)]
    assert len(errors) == 1 and "max_iterations" in errors[0].message
    assert provider.call_count == 3


async def test_no_tool_specs_passed_when_registry_empty(vault: VaultService):
    provider = ScriptedProvider([[TextDelta("ok"), Usage(1, 1, None)]])
    agent = AgentLoop(llm=provider, tools=ToolRegistry(), vault=vault)

    await _collect(agent, "hi")

    # Passing tools=None (not []) lets providers skip the tools field entirely.
    assert provider.tool_calls_seen[0] is None


async def test_system_prompt_includes_memory_and_preferences(vault: VaultService):
    vault.write(
        "memory.md",
        "# Memory\nThe user's partner is Alice.\n",
        actor="user",
    )
    vault.write(
        "preferences.md",
        "# Preferences\nReply concisely.\n",
        actor="user",
    )
    agent = AgentLoop(
        llm=ScriptedProvider([[TextDelta("x"), Usage(0, 0, None)]]),
        tools=ToolRegistry(),
        vault=vault,
    )
    messages = agent._build_context("hello", [])
    assert messages[0].role == "system"
    assert "Alice" in messages[0].content
    assert "concisely" in messages[0].content
    assert messages[-1].role == "user" and messages[-1].content == "hello"


async def test_system_prompt_handles_missing_files(tmp_path):
    vault_root = tmp_path / "empty-vault"
    vault_root.mkdir()
    vault = VaultService(vault_root)  # no bootstrap — memory.md missing
    agent = AgentLoop(
        llm=ScriptedProvider([[Usage(0, 0, None)]]),
        tools=ToolRegistry(),
        vault=vault,
    )
    messages = agent._build_context("hi", [])
    assert "(empty)" in messages[0].content


async def test_system_prompt_lists_vault_contents(vault: VaultService):
    # vault fixture bootstraps the three stubs; plus add a custom file.
    vault.write("bio.md", "# Bio\nCall me Philip.\n", actor="user")
    agent = AgentLoop(
        llm=ScriptedProvider([[Usage(0, 0, None)]]),
        tools=ToolRegistry(),
        vault=vault,
    )
    prompt = agent._build_context("hi", [])[0].content
    # Each top-level file should appear in the orientation listing.
    assert "- bio.md" in prompt
    assert "- memory.md" in prompt
    assert "- todos.md" in prompt
    # `.git` is noise, don't leak it into the prompt.
    assert ".git" not in prompt


async def test_system_prompt_instructs_tool_use_before_giving_up(vault: VaultService):
    agent = AgentLoop(
        llm=ScriptedProvider([[Usage(0, 0, None)]]),
        tools=ToolRegistry(),
        vault=vault,
    )
    prompt = agent._build_context("hi", [])[0].content
    # Key phrases that push the model toward search-before-ignorance.
    assert "search_vault" in prompt
    assert "check before answering" in prompt.lower() or "look" in prompt.lower()


async def test_system_prompt_includes_assistant_name_default(vault: VaultService):
    agent = AgentLoop(
        llm=ScriptedProvider([[Usage(0, 0, None)]]),
        tools=ToolRegistry(),
        vault=vault,
    )
    prompt = agent._build_context("hi", [])[0].content
    assert "Your name is Bengt" in prompt


async def test_system_prompt_uses_custom_assistant_name(vault: VaultService):
    agent = AgentLoop(
        llm=ScriptedProvider([[Usage(0, 0, None)]]),
        tools=ToolRegistry(),
        vault=vault,
        assistant_name="Miles",
    )
    prompt = agent._build_context("hi", [])[0].content
    assert "Your name is Miles" in prompt
    assert "Bengt" not in prompt


async def test_system_prompt_tells_agent_to_save_proactively(vault: VaultService):
    agent = AgentLoop(
        llm=ScriptedProvider([[Usage(0, 0, None)]]),
        tools=ToolRegistry(),
        vault=vault,
    )
    prompt = agent._build_context("hi", [])[0].content
    # Memory policy must mention destination files + concrete tool to use.
    assert "memory.md" in prompt
    assert "preferences.md" in prompt
    assert "append_to_file" in prompt
    assert "proactively" in prompt.lower() or "without being asked" in prompt.lower()


async def test_history_threads_between_user_and_system(vault: VaultService):
    provider = ScriptedProvider([[TextDelta("k"), Usage(0, 0, None)]])
    agent = AgentLoop(llm=provider, tools=ToolRegistry(), vault=vault)
    history = [
        Message(role="user", content="first"),
        Message(role="assistant", content="reply"),
    ]
    [_ async for _ in agent.run("latest", history=history)]
    sent = provider.calls[0]
    assert [m.role for m in sent] == ["system", "user", "assistant", "user"]
    assert sent[1].content == "first"
    assert sent[-1].content == "latest"


async def test_mock_tools_registry():
    from app.agent import register_mock_tools

    reg = ToolRegistry()
    register_mock_tools(reg)
    assert set(reg.names()) == {"echo", "current_time", "add"}
    assert await reg.invoke("echo", {"message": "hi"}) == "hi"
    assert await reg.invoke("add", {"a": 2, "b": 3}) == "5"
    assert await reg.invoke("add", {"a": 1.5, "b": 0.5}) == "2"
    time_str = await reg.invoke("current_time", {})
    # ISO 8601 UTC: YYYY-MM-DDTHH:MM:SS+00:00
    assert "T" in time_str and time_str.endswith("+00:00")


async def test_unknown_tool_name_raises():
    from app.agent.tools import UnknownToolError

    reg = ToolRegistry()
    with pytest.raises(UnknownToolError):
        await reg.invoke("nope", {})
