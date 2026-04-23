"""Vault-backed tools (PRD §4.3). Registered into the agent's ToolRegistry.

All writes use actor="agent" so the vault's git history attributes the
change correctly and the audit trail is honest.
"""

from datetime import date
from typing import Any

from app.agent.tools import Tool, ToolRegistry
from app.indexer import Indexer
from app.vault import NotFoundError, VaultService
from app.vault.todos import parse_todos


def register_vault_tools(
    registry: ToolRegistry,
    vault: VaultService,
    indexer: Indexer,
) -> None:
    async def search_vault(args: dict[str, Any]) -> str:
        query = str(args["query"])
        limit = int(args.get("limit", 5))
        hits = indexer.search(query, limit=limit)
        if not hits:
            return "(no results)"
        return "\n\n".join(f"--- {h.path} ---\n{h.snippet}" for h in hits)

    async def list_vault(args: dict[str, Any]) -> str:
        path = str(args.get("path", "") or "")
        entries = vault.list(path)
        if not entries:
            return "(empty)"
        return "\n".join(
            f"{'DIR ' if e.is_dir else 'FILE'} {e.path}" for e in entries
        )

    async def read_file(args: dict[str, Any]) -> str:
        return vault.read(str(args["path"]))

    async def write_file(args: dict[str, Any]) -> str:
        path = str(args["path"])
        vault.write(path, str(args["content"]), actor="agent")
        return f"wrote {path}"

    async def edit_file(args: dict[str, Any]) -> str:
        path = str(args["path"])
        vault.edit(
            path,
            str(args["old_string"]),
            str(args["new_string"]),
            actor="agent",
        )
        return f"edited {path}"

    async def append_to_file(args: dict[str, Any]) -> str:
        path = str(args["path"])
        vault.append(path, str(args["content"]), actor="agent")
        return f"appended to {path}"

    async def list_todos(args: dict[str, Any]) -> str:
        filter_ = str(args.get("filter", "") or "").strip().lower()
        try:
            content = vault.read("todos.md")
        except NotFoundError:
            return "(no todos.md yet)"
        todos = parse_todos(content)
        today = date.today()

        def keep(t) -> bool:
            if filter_ in ("", "all"):
                return True
            if filter_ == "open":
                return not t.done
            if filter_ == "done":
                return t.done
            if filter_ == "today":
                return not t.done and t.due == today
            if filter_ == "overdue":
                return not t.done and t.due is not None and t.due < today
            if filter_ == "upcoming":
                return not t.done and t.due is not None and t.due >= today
            # Unknown filter — show all.
            return True

        filtered = [t for t in todos if keep(t)]
        if not filtered:
            return "(no todos match)"
        lines: list[str] = []
        for t in filtered:
            parts = ["[x]" if t.done else "[ ]", t.text]
            if t.due:
                parts.append(f"📅 {t.due.isoformat()}")
            if t.priority:
                parts.append(f"({t.priority})")
            if t.tags:
                parts.append(" ".join(f"#{x}" for x in t.tags))
            lines.append(" ".join(parts))
        return "\n".join(lines)

    registry.register(
        Tool(
            name="search_vault",
            description=(
                "Semantic search across the vault. Use this when the user asks about "
                "something they've previously noted, or when you need to recall context."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural-language query."},
                    "limit": {
                        "type": "integer",
                        "description": "Max number of hits (default 5).",
                        "minimum": 1,
                        "maximum": 20,
                    },
                },
                "required": ["query"],
            },
            fn=search_vault,
        )
    )
    registry.register(
        Tool(
            name="list_vault",
            description=(
                "List files and directories under a vault path. Use to discover "
                "what notes exist. Empty `path` lists the vault root."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path relative to vault root. Empty for root.",
                    },
                },
            },
            fn=list_vault,
        )
    )
    registry.register(
        Tool(
            name="read_file",
            description="Read the full contents of a file in the vault.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to vault root."},
                },
                "required": ["path"],
            },
            fn=read_file,
        )
    )
    registry.register(
        Tool(
            name="write_file",
            description=(
                "Create a new file OR fully overwrite an existing one. For small, "
                "targeted changes to a large file, prefer `edit_file` to save tokens."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            fn=write_file,
        )
    )
    registry.register(
        Tool(
            name="edit_file",
            description=(
                "Make a targeted edit by replacing exact text. `old_string` must "
                "appear EXACTLY ONCE in the file — include enough surrounding context "
                "to make it unique."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {
                        "type": "string",
                        "description": "Exact text to find (must match exactly once).",
                    },
                    "new_string": {"type": "string", "description": "Replacement text."},
                },
                "required": ["path", "old_string", "new_string"],
            },
            fn=edit_file,
        )
    )
    registry.register(
        Tool(
            name="list_todos",
            description=(
                "List structured todos from todos.md with optional filter. "
                "Filter values: 'all' (default), 'open', 'done', 'today' "
                "(open and due today), 'overdue' (open and due before today), "
                "'upcoming' (open and due today-or-later). Prefer this over "
                "read_file for answering 'what do I need to do?' questions — "
                "it parses dates and priorities."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "enum": ["all", "open", "done", "today", "overdue", "upcoming"],
                        "description": "Filter which todos to show.",
                    },
                },
            },
            fn=list_todos,
        )
    )
    registry.register(
        Tool(
            name="append_to_file",
            description=(
                "Append content to the end of a file. Creates the file if it doesn't "
                "exist. Good for adding todos or log entries without rewriting the file."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            fn=append_to_file,
        )
    )
