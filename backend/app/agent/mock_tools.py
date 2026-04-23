"""Mock tools used for step 5. Replaced with real vault/scheduling tools
in step 6; kept here so the loop can be exercised before those land.
"""

from datetime import datetime, timezone
from typing import Any

from app.agent.tools import Tool, ToolRegistry


async def _echo(arguments: dict[str, Any]) -> str:
    return str(arguments.get("message", ""))


async def _current_time(arguments: dict[str, Any]) -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _add(arguments: dict[str, Any]) -> str:
    a = float(arguments["a"])
    b = float(arguments["b"])
    total = a + b
    if total.is_integer():
        return str(int(total))
    return str(total)


def register_mock_tools(registry: ToolRegistry) -> None:
    registry.register(
        Tool(
            name="echo",
            description="Echo back the given message verbatim. Useful for testing.",
            parameters={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "text to echo"},
                },
                "required": ["message"],
            },
            fn=_echo,
        )
    )
    registry.register(
        Tool(
            name="current_time",
            description="Get the current date and time in ISO 8601 UTC format.",
            parameters={"type": "object", "properties": {}},
            fn=_current_time,
        )
    )
    registry.register(
        Tool(
            name="add",
            description="Add two numbers together. Returns the sum as a string.",
            parameters={
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
            fn=_add,
        )
    )
