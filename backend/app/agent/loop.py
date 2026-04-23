from collections.abc import AsyncIterator
from datetime import date

from app.agent.events import (
    AgentDone,
    AgentError,
    AgentEvent,
    AgentText,
    AgentToolResult,
    AgentToolStart,
    AgentTurnEnd,
    AgentUsage,
)
from app.agent.tools import ToolRegistry
from app.budget import BudgetService
from app.db import AuditService
from app.llm import LLMProvider, Message, TextDelta, ToolCall, ToolCallEvent, Usage
from app.vault import NotFoundError, VaultService

_SYSTEM_PROMPT = """\
You are a personal AI assistant — a "second brain" for a single user. Your job is to help them stay organized, recall what they've written, and handle ongoing tasks.

You have tools for searching, reading, and writing a markdown vault that holds the user's notes, todos, memory, and preferences. Use them freely when helpful. Prefer concise, direct replies. When you don't know, say so — don't guess.

Long-term memory about the user (from memory.md):
---
{memory}
---

User preferences (from preferences.md):
---
{preferences}
---

Today's date: {today}
"""


class AgentLoop:
    """ReAct-style loop: stream LLM → collect tool calls → execute → feed back → repeat.

    Emits agent-level events (see app.agent.events) so callers (WebSocket in
    step 9, tests now) can render progress and persist transcripts.

    If `audit` is wired, every LLM iteration and tool invocation is logged.
    If `budget` is wired, the loop refuses to start a new iteration once the
    daily cap is spent.
    """

    def __init__(
        self,
        llm: LLMProvider,
        tools: ToolRegistry,
        vault: VaultService,
        max_iterations: int = 10,
        audit: AuditService | None = None,
        budget: BudgetService | None = None,
    ):
        self.llm = llm
        self.tools = tools
        self.vault = vault
        self.max_iterations = max_iterations
        self.audit = audit
        self.budget = budget

    async def run(
        self,
        user_message: str,
        history: list[Message] | None = None,
        conversation_id: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        messages = self._build_context(user_message, history or [])
        tool_specs = self.tools.specs() or None

        for _ in range(self.max_iterations):
            # Check the budget before each LLM call — stops a runaway agent
            # from burning dollars across multiple iterations.
            if self.budget and self.budget.exceeded():
                status = self.budget.status()
                yield AgentError(
                    message=(
                        f"Daily budget exceeded "
                        f"(${status.spent_usd:.4f} of ${status.cap_usd:.2f}). "
                        "Try again after UTC midnight."
                    )
                )
                return

            collected: list[ToolCall] = []
            text_chunks: list[str] = []
            async for event in self.llm.stream(messages, tools=tool_specs):
                if isinstance(event, TextDelta):
                    text_chunks.append(event.text)
                    yield AgentText(text=event.text)
                elif isinstance(event, ToolCallEvent):
                    collected.append(event.tool_call)
                elif isinstance(event, Usage):
                    if self.audit:
                        self.audit.record_llm_call(
                            provider=self.llm.name,
                            model=self.llm.model,
                            input_tokens=event.input_tokens,
                            output_tokens=event.output_tokens,
                            cost_usd=event.cost_usd,
                            conversation_id=conversation_id,
                        )
                    yield AgentUsage(
                        input_tokens=event.input_tokens,
                        output_tokens=event.output_tokens,
                        cost_usd=event.cost_usd,
                    )

            turn_text = "".join(text_chunks)
            yield AgentTurnEnd(text=turn_text, tool_calls=list(collected))

            if not collected:
                yield AgentDone()
                return

            messages.append(
                Message(role="assistant", content=turn_text, tool_calls=collected)
            )

            for tc in collected:
                yield AgentToolStart(
                    call_id=tc.id, name=tc.name, arguments=tc.arguments
                )
                try:
                    result = await self.tools.invoke(tc.name, tc.arguments)
                    if self.audit:
                        self.audit.record_tool_invocation(
                            name=tc.name,
                            arguments=tc.arguments,
                            result=result,
                            error=False,
                            conversation_id=conversation_id,
                        )
                    yield AgentToolResult(call_id=tc.id, result=result, error=False)
                    messages.append(
                        Message(role="tool", content=result, tool_call_id=tc.id)
                    )
                except Exception as exc:
                    error_text = f"Tool '{tc.name}' failed: {exc}"
                    if self.audit:
                        self.audit.record_tool_invocation(
                            name=tc.name,
                            arguments=tc.arguments,
                            result=error_text,
                            error=True,
                            conversation_id=conversation_id,
                        )
                    yield AgentToolResult(
                        call_id=tc.id, result=error_text, error=True
                    )
                    messages.append(
                        Message(role="tool", content=error_text, tool_call_id=tc.id)
                    )

        yield AgentError(
            message=(
                f"Agent reached max_iterations ({self.max_iterations}) "
                "without producing a final response."
            )
        )

    def _build_context(
        self, user_message: str, history: list[Message]
    ) -> list[Message]:
        memory = self._safe_read("memory.md")
        preferences = self._safe_read("preferences.md")
        system = _SYSTEM_PROMPT.format(
            memory=memory or "(empty)",
            preferences=preferences or "(empty)",
            today=date.today().isoformat(),
        )
        return [
            Message(role="system", content=system),
            *history,
            Message(role="user", content=user_message),
        ]

    def _safe_read(self, path: str) -> str:
        try:
            return self.vault.read(path).strip()
        except NotFoundError:
            return ""
