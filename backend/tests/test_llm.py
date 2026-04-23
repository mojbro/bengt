import json

import pytest

from app.config import Settings
from app.llm import (
    Message,
    ToolCall,
    ToolSpec,
    build_provider,
    estimate_cost,
)
from app.llm.factory import LLMConfigError
from app.llm.openai_provider import OpenAIProvider


def test_message_translation_user():
    m = Message(role="user", content="hi")
    assert OpenAIProvider._to_wire_message(m) == {"role": "user", "content": "hi"}


def test_message_translation_tool_result():
    m = Message(role="tool", content="result", tool_call_id="call_abc")
    assert OpenAIProvider._to_wire_message(m) == {
        "role": "tool",
        "content": "result",
        "tool_call_id": "call_abc",
    }


def test_message_translation_assistant_with_tool_calls():
    m = Message(
        role="assistant",
        content="",
        tool_calls=[ToolCall(id="call_1", name="search", arguments={"q": "volvo"})],
    )
    wire = OpenAIProvider._to_wire_message(m)
    assert wire["role"] == "assistant"
    assert wire["content"] == ""
    assert wire["tool_calls"] == [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "search", "arguments": json.dumps({"q": "volvo"})},
        }
    ]


def test_tool_spec_translation():
    t = ToolSpec(
        name="search_vault",
        description="Search the vault",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}},
    )
    assert OpenAIProvider._to_wire_tool(t) == {
        "type": "function",
        "function": {
            "name": "search_vault",
            "description": "Search the vault",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
        },
    }


def test_pricing_known_model():
    cost = estimate_cost("openai", "gpt-4o-mini", 1_000_000, 1_000_000)
    assert cost == pytest.approx(0.15 + 0.60)


def test_pricing_unknown_model():
    assert estimate_cost("openai", "gpt-9999", 100, 100) is None
    assert estimate_cost("anthropic", "claude", 100, 100) is None


def test_factory_builds_openai():
    s = Settings(llm_provider="openai", llm_api_key="sk-test", llm_model="gpt-4o")
    p = build_provider(s)
    assert p.name == "openai"
    assert p.model == "gpt-4o"


def test_factory_rejects_missing_key():
    s = Settings(llm_provider="openai", llm_api_key="", llm_model="gpt-4o")
    with pytest.raises(LLMConfigError, match="LLM_API_KEY"):
        build_provider(s)


def test_factory_rejects_unknown_provider():
    s = Settings(llm_provider="gemini", llm_api_key="x", llm_model="y")
    with pytest.raises(LLMConfigError, match="Unknown LLM provider"):
        build_provider(s)


def test_factory_provider_name_case_insensitive():
    s = Settings(llm_provider="OpenAI", llm_api_key="sk-test", llm_model="gpt-4o")
    p = build_provider(s)
    assert p.name == "openai"
