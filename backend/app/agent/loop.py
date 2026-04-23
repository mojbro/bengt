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

The user's notes, facts about them, preferences, todos, and anything they've ever asked you to remember live in a markdown vault. You have tools to explore and change it:

- `search_vault(query)` — semantic search across the whole vault. Prefer this when you need to recall something.
- `list_vault(path)` / `read_file(path)` — navigate and read specific files.
- `write_file` / `edit_file` / `append_to_file` — make changes (e.g. updating memory.md, adding todos).
- `schedule_job(when, instruction)` / `list_scheduled_jobs` / `cancel_job` — set up future reminders or recurring checks.

**Tool-use policy:** if the user asks about themselves, their history, or anything that could plausibly be in the vault, check before answering. Specifically:
- If the content you need isn't already in the memory/preferences dump below, search the vault. Look at the "Current vault contents" list to decide where to look first — e.g. a question about the user's background likely lives in a file like bio.md or similar.
- Don't say "I don't know" until you've actually tried a `search_vault` or read a plausibly-related file.
- Prefer concise, direct replies once you have the answer.

Long-term memory about the user (from memory.md):
---
{memory}
---

User preferences (from preferences.md):
---
{preferences}
---

Current vault contents (top-level, for orientation):
{vault_listing}

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
            vault_listing=self._vault_listing(),
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

    def _vault_listing(self) -> str:
        """Top-level vault entries formatted for the system prompt.

        Gives the model a cheap prior on what files/dirs exist so it can
        decide which to read without a discovery round-trip. Deep trees
        stay out — the agent can `list_vault(path)` to drill in.
        """
        try:
            entries = self.vault.list("")
        except Exception:
            return "(unavailable)"
        lines: list[str] = []
        for entry in entries:
            if entry.path == ".git":
                continue
            suffix = "/" if entry.is_dir else ""
            lines.append(f"- {entry.path}{suffix}")
        return "\n".join(lines) if lines else "(empty)"
