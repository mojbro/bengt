"""Wires a scheduled job firing → agent invocation → persistence → UI push.

APScheduler calls the module-level `fire_scheduled_job` coroutine when a
job's trigger fires. We need service handles inside that callable but can't
pass live objects through APScheduler's kwargs (not pickleable under a
persistent job store), so there's a tiny module-level service registry set
up once at lifespan startup.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.agent import AgentLoop, AgentToolResult, AgentTurnEnd
from app.db import ConversationService
from app.ws_manager import ConnectionManager

log = logging.getLogger(__name__)


@dataclass
class SchedulerServices:
    agent: AgentLoop
    conversations: ConversationService
    ws_manager: ConnectionManager
    scheduled_conversation_id: str


_services: SchedulerServices | None = None


def register_services(services: SchedulerServices) -> None:
    global _services
    _services = services


def clear_services() -> None:
    global _services
    _services = None


async def fire_scheduled_job(instruction: str) -> None:
    """Invoked by APScheduler when a trigger fires."""
    if _services is None:
        log.warning(
            "fire_scheduled_job called before services were registered; "
            "instruction dropped: %r",
            instruction,
        )
        return

    svc = _services
    conv_id = svc.scheduled_conversation_id

    # Front the message with a marker so the user can tell this came from
    # a trigger rather than their own input.
    framed = f"(scheduled reminder) {instruction}"

    history = svc.conversations.to_llm_messages(conv_id)
    svc.conversations.append_message(conv_id, "user", framed)

    try:
        async for event in svc.agent.run(framed, history=history):
            if isinstance(event, AgentTurnEnd):
                if event.text or event.tool_calls:
                    svc.conversations.append_message(
                        conv_id,
                        "assistant",
                        content=event.text,
                        tool_calls=event.tool_calls or None,
                    )
            elif isinstance(event, AgentToolResult):
                svc.conversations.append_message(
                    conv_id,
                    "tool",
                    content=event.result,
                    tool_call_id=event.call_id,
                )
    except Exception:
        log.exception("scheduled job execution failed: %r", instruction)
        svc.conversations.append_message(
            conv_id,
            "assistant",
            content=f"Scheduled job failed: {instruction!r}",
        )

    await svc.ws_manager.broadcast(
        {
            "type": "notification",
            "kind": "scheduled_fired",
            "conversation_id": conv_id,
            "instruction": instruction,
        }
    )
