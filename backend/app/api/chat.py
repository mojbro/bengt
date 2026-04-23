"""WebSocket streaming chat.

Wire protocol (JSON, both directions):

  client → server:
    {"conversation_id": "<uuid>", "content": "<text>"}

  server → client (event-by-event as they stream):
    {"type": "text",        "text": "..."}
    {"type": "tool_start",  "call_id": "...", "name": "...", "arguments": {...}}
    {"type": "tool_result", "call_id": "...", "result": "...", "error": bool}
    {"type": "usage",       "input_tokens": n, "output_tokens": n, "cost_usd": n|null}
    {"type": "done"}
    {"type": "error", "message": "..."}

Auth is via the session cookie set by /api/auth/login. Unauthenticated
connections are closed with policy-violation (1008) before accept.
"""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.agent import (
    AgentDone,
    AgentError,
    AgentText,
    AgentToolResult,
    AgentToolStart,
    AgentTurnEnd,
    AgentUsage,
)
from app.db import NotFoundError
from app.titling import maybe_auto_title

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _event_to_wire(event: Any) -> dict[str, Any] | None:
    if isinstance(event, AgentText):
        return {"type": "text", "text": event.text}
    if isinstance(event, AgentToolStart):
        return {
            "type": "tool_start",
            "call_id": event.call_id,
            "name": event.name,
            "arguments": event.arguments,
        }
    if isinstance(event, AgentToolResult):
        return {
            "type": "tool_result",
            "call_id": event.call_id,
            "result": event.result,
            "error": event.error,
        }
    if isinstance(event, AgentUsage):
        return {
            "type": "usage",
            "input_tokens": event.input_tokens,
            "output_tokens": event.output_tokens,
            "cost_usd": event.cost_usd,
        }
    if isinstance(event, AgentDone):
        return {"type": "done"}
    if isinstance(event, AgentError):
        return {"type": "error", "message": event.message}
    # AgentTurnEnd is persistence-only, not sent over the wire.
    return None


@router.websocket("/ws")
async def chat_ws(websocket: WebSocket) -> None:
    # Auth before accept so unauthed clients can't open the socket.
    if not websocket.session.get("authed"):
        await websocket.close(code=1008, reason="not authenticated")
        return

    await websocket.accept()

    agent = websocket.app.state.agent
    conversations = websocket.app.state.conversations
    ws_manager = websocket.app.state.ws_manager
    settings = websocket.app.state.settings
    audit = getattr(websocket.app.state, "audit", None)
    llm = websocket.app.state.llm
    ws_manager.add(websocket)

    try:
        while True:
            data = await websocket.receive_json()

            # Keepalive pings from the client — sent periodically to prevent
            # idle timeouts on intermediate proxies. Just absorb them.
            if isinstance(data, dict) and data.get("type") == "ping":
                continue

            conv_id = data.get("conversation_id")
            content = data.get("content")
            if not isinstance(conv_id, str) or not isinstance(content, str):
                await websocket.send_json(
                    {"type": "error", "message": "expected {conversation_id, content}"}
                )
                continue

            # Validate the conversation exists before touching anything.
            try:
                conversations.get(conv_id)
            except NotFoundError:
                await websocket.send_json(
                    {"type": "error", "message": f"conversation {conv_id!r} not found"}
                )
                continue

            # Load history BEFORE appending the new user message (so we
            # don't feed the same message twice — AgentLoop adds it itself).
            history = conversations.to_llm_messages(conv_id)
            conversations.append_message(conv_id, "user", content)

            try:
                async for event in agent.run(
                    content, history=history, conversation_id=conv_id
                ):
                    wire = _event_to_wire(event)
                    if wire is not None:
                        await websocket.send_json(wire)

                    if isinstance(event, AgentTurnEnd):
                        if event.text or event.tool_calls:
                            conversations.append_message(
                                conv_id,
                                "assistant",
                                content=event.text,
                                tool_calls=event.tool_calls or None,
                            )
                    elif isinstance(event, AgentToolResult):
                        conversations.append_message(
                            conv_id,
                            "tool",
                            content=event.result,
                            tool_call_id=event.call_id,
                        )
            except Exception as exc:  # noqa: BLE001 — surface to client
                log.exception("chat turn failed")
                await websocket.send_json(
                    {"type": "error", "message": f"agent error: {exc}"}
                )

            # Fire-and-forget title generation — if this is a fresh
            # conversation, propose a descriptive name so "New thread"
            # doesn't hang around in the sidebar. Runs off the hot path
            # so it doesn't add latency to the user's reply.
            if settings.auto_title:
                asyncio.create_task(
                    maybe_auto_title(
                        conv_id=conv_id,
                        conversations=conversations,
                        llm=llm,
                        audit=audit,
                        ws_manager=ws_manager,
                    )
                )
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.remove(websocket)
