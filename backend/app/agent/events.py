from dataclasses import dataclass, field
from typing import Any

from app.llm import ToolCall


@dataclass(frozen=True)
class AgentText:
    """A chunk of the agent's final-text response, streamed."""

    text: str


@dataclass(frozen=True)
class AgentToolStart:
    """Emitted just before a tool is executed."""

    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class AgentToolResult:
    """Emitted after a tool finishes (success or handled error)."""

    call_id: str
    result: str
    error: bool = False


@dataclass(frozen=True)
class AgentUsage:
    """LLM token + cost usage from one iteration of the loop."""

    input_tokens: int
    output_tokens: int
    cost_usd: float | None


@dataclass(frozen=True)
class AgentError:
    """Terminal error (e.g. max_iterations reached)."""

    message: str


@dataclass(frozen=True)
class AgentTurnEnd:
    """Emitted after each LLM iteration's stream completes.

    Gives persistence consumers a single point to save the assistant turn
    (with its accumulated text and any tool calls the LLM decided to make).
    """

    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(frozen=True)
class AgentDone:
    """Normal end of a turn."""


AgentEvent = (
    AgentText
    | AgentToolStart
    | AgentToolResult
    | AgentUsage
    | AgentTurnEnd
    | AgentError
    | AgentDone
)
