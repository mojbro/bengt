import json
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from app.llm.pricing import estimate_cost
from app.llm.types import (
    Message,
    StreamEvent,
    TextDelta,
    ToolCall,
    ToolCallEvent,
    ToolSpec,
    Usage,
)


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str):
        self._client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [self._to_wire_message(m) for m in messages],
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = [self._to_wire_tool(t) for t in tools]

        stream = await self._client.chat.completions.create(**kwargs)

        # Tool calls arrive as deltas indexed by position; accumulate until flush.
        tool_buffer: dict[int, dict[str, Any]] = {}

        async for chunk in stream:
            if chunk.usage is not None:
                yield Usage(
                    input_tokens=chunk.usage.prompt_tokens,
                    output_tokens=chunk.usage.completion_tokens,
                    cost_usd=estimate_cost(
                        self.name,
                        self.model,
                        chunk.usage.prompt_tokens,
                        chunk.usage.completion_tokens,
                    ),
                )
                continue

            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta

            if delta.content:
                yield TextDelta(text=delta.content)

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    buf = tool_buffer.setdefault(
                        tc.index, {"id": "", "name": "", "arguments": ""}
                    )
                    if tc.id:
                        buf["id"] = tc.id
                    if tc.function is not None:
                        if tc.function.name:
                            buf["name"] = tc.function.name
                        if tc.function.arguments:
                            buf["arguments"] += tc.function.arguments

            if choice.finish_reason == "tool_calls" and tool_buffer:
                for idx in sorted(tool_buffer.keys()):
                    buf = tool_buffer[idx]
                    try:
                        args = json.loads(buf["arguments"] or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    yield ToolCallEvent(
                        tool_call=ToolCall(
                            id=buf["id"],
                            name=buf["name"],
                            arguments=args,
                        )
                    )
                tool_buffer.clear()

    @staticmethod
    def _to_wire_message(m: Message) -> dict[str, Any]:
        if m.role == "tool":
            return {
                "role": "tool",
                "content": m.content,
                "tool_call_id": m.tool_call_id,
            }
        out: dict[str, Any] = {"role": m.role, "content": m.content}
        if m.tool_calls:
            out["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in m.tool_calls
            ]
        return out

    @staticmethod
    def _to_wire_tool(t: ToolSpec) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
