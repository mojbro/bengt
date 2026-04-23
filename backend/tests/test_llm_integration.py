"""Real-API integration tests for the LLM layer.

Skipped by default. Run with:

    docker compose exec backend pytest -m integration -v

These hit the real provider configured in `.env` (LLM_PROVIDER / LLM_MODEL /
LLM_API_KEY) and therefore cost a few cents per run. Keep the prompts tiny.
"""

import pytest

from app.config import Settings
from app.llm import (
    Message,
    TextDelta,
    ToolCallEvent,
    ToolSpec,
    Usage,
    build_provider,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not Settings().llm_api_key,
        reason="LLM_API_KEY is empty — integration tests need a real key",
    ),
]


async def test_streams_text_from_real_api():
    provider = build_provider(Settings())
    events = []
    async for event in provider.stream(
        [Message(role="user", content="Say the single word 'hello' and nothing else.")]
    ):
        events.append(event)

    text_events = [e for e in events if isinstance(e, TextDelta)]
    usage_events = [e for e in events if isinstance(e, Usage)]

    assert text_events, f"expected TextDelta events, got {events!r}"
    text = "".join(e.text for e in text_events).strip()
    assert text, "expected non-empty text content"

    assert len(usage_events) == 1, f"expected exactly one Usage, got {usage_events!r}"
    usage = usage_events[0]
    assert usage.input_tokens > 0
    assert usage.output_tokens > 0


async def test_tool_call_round_trip_from_real_api():
    provider = build_provider(Settings())
    tools = [
        ToolSpec(
            name="echo",
            description="Echo back the message given to you. Use this tool now.",
            parameters={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "text to echo"},
                },
                "required": ["message"],
            },
        )
    ]
    messages = [
        Message(
            role="system",
            content=(
                "You must call the `echo` tool with message='hello world'. "
                "Do not respond in plain text; only call the tool."
            ),
        ),
        Message(role="user", content="Go."),
    ]

    events = []
    async for event in provider.stream(messages, tools):
        events.append(event)

    tool_events = [e for e in events if isinstance(e, ToolCallEvent)]
    assert tool_events, f"expected the model to call `echo`; got events: {events!r}"
    first = tool_events[0].tool_call
    assert first.name == "echo"
    assert "message" in first.arguments
    assert isinstance(first.arguments["message"], str)
    assert first.arguments["message"].strip(), "echoed message should be non-empty"
