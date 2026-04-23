from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal, Protocol

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str = ""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolCallEvent:
    tool_call: ToolCall


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int
    cost_usd: float | None


StreamEvent = TextDelta | ToolCallEvent | Usage


class LLMProvider(Protocol):
    """Provider-agnostic streaming chat interface.

    Implementations translate to/from their native wire formats. Nothing
    OpenAI-specific leaks out through this protocol.
    """

    name: str
    model: str

    def stream(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        ...
