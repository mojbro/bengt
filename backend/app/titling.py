"""Auto-title freshly-created conversations after the first real turn.

Runs in the background (fire-and-forget from the chat WS handler) so it
adds zero latency to the user's reply. When done, broadcasts a
`conversation_renamed` notification over the ws_manager so the UI picks
up the new title without a full reload.
"""

from __future__ import annotations

import logging

from app.db import ConversationService, NotFoundError
from app.db.audit import AuditService
from app.llm import LLMProvider, Message, TextDelta, Usage
from app.ws_manager import ConnectionManager

log = logging.getLogger(__name__)

_DEFAULT_TITLES = {"New thread", "New chat", ""}
_MAX_TITLE_LENGTH = 80

_SYSTEM_PROMPT = (
    "You generate short, descriptive titles for chat conversations. "
    "Given the transcript below, propose a 2-6 word title that captures the "
    "topic. Respond with ONLY the title text: no quotes, no preamble, no "
    "trailing punctuation."
)


def _clean_title(raw: str) -> str:
    title = raw.strip()
    # Strip surrounding quotes that the model sometimes adds anyway.
    for quote_char in ('"', "'", "`"):
        if title.startswith(quote_char) and title.endswith(quote_char):
            title = title[1:-1].strip()
    # Drop a trailing period; titles shouldn't end in one.
    if title.endswith("."):
        title = title[:-1].rstrip()
    # One line, hard cap.
    title = title.splitlines()[0] if title else ""
    return title[:_MAX_TITLE_LENGTH].strip()


async def maybe_auto_title(
    conv_id: str,
    conversations: ConversationService,
    llm: LLMProvider,
    audit: AuditService | None,
    ws_manager: ConnectionManager | None,
) -> None:
    """Generate a title for `conv_id` if it still has the default title.

    Safe to call after every turn; idempotent — once a real title lands,
    subsequent calls return early.
    """
    try:
        conv = conversations.get(conv_id)
    except NotFoundError:
        return
    if conv.title.strip() not in _DEFAULT_TITLES:
        return

    msgs = conversations.messages(conv_id)
    has_user = any(m.role == "user" and (m.content or "").strip() for m in msgs)
    has_assistant = any(
        m.role == "assistant" and (m.content or "").strip() for m in msgs
    )
    if not (has_user and has_assistant):
        return

    # Build a compact transcript — first user + first assistant is usually
    # enough to judge the topic, but we'll cap at four exchanges just in
    # case the auto-title runs late.
    transcript_lines: list[str] = []
    for m in msgs[:8]:
        text = (m.content or "").strip()
        if not text or m.role == "tool":
            continue
        transcript_lines.append(f"{m.role}: {text[:400]}")
    if not transcript_lines:
        return

    prompt = [
        Message(role="system", content=_SYSTEM_PROMPT),
        Message(role="user", content="\n".join(transcript_lines)),
    ]

    try:
        text_chunks: list[str] = []
        usage: Usage | None = None
        async for event in llm.stream(prompt, tools=None):
            if isinstance(event, TextDelta):
                text_chunks.append(event.text)
            elif isinstance(event, Usage):
                usage = event
    except Exception:
        log.exception("auto-title LLM call failed for %s", conv_id)
        return

    if usage and audit is not None:
        audit.record_llm_call(
            provider=llm.name,
            model=llm.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=usage.cost_usd,
            conversation_id=conv_id,
        )

    title = _clean_title("".join(text_chunks))
    if not title or title in _DEFAULT_TITLES:
        return

    try:
        conversations.rename(conv_id, title)
    except NotFoundError:
        return

    if ws_manager is not None:
        await ws_manager.broadcast(
            {
                "type": "notification",
                "kind": "conversation_renamed",
                "conversation_id": conv_id,
                "title": title,
            }
        )
