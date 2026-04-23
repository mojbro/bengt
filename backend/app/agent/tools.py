from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.llm import ToolSpec

ToolFn = Callable[[dict[str, Any]], Awaitable[str]]


class UnknownToolError(KeyError):
    """Raised when the agent tries to invoke a tool that isn't registered."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    fn: ToolFn


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(name=t.name, description=t.description, parameters=t.parameters)
            for t in self._tools.values()
        ]

    async def invoke(self, name: str, arguments: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            raise UnknownToolError(name)
        return await tool.fn(arguments)
