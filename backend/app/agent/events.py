from dataclasses import dataclass
from typing import Any


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
class AgentDone:
    """Normal end of a turn."""


AgentEvent = (
    AgentText
    | AgentToolStart
    | AgentToolResult
    | AgentUsage
    | AgentError
    | AgentDone
)
