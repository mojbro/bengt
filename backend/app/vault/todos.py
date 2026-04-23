"""Obsidian Tasks parser and serializer for todos.md.

Source of truth stays the markdown file; this module just renders its
contents as a structured list (with due dates, priorities, tags, etc.)
so the UI and agent tools can operate on it without re-parsing in ten
places.

Format (PRD §4.2):
  - [ ] Call Volvo about contract 📅 2026-04-25 🔼 #work @erik
  - [x] Send invoice ✅ 2026-04-22

Priority emojis (Obsidian Tasks convention):
  🔺 highest, ⏫ high, 🔼 medium, 🔽 low, ⏬ lowest
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date

PRIORITY_EMOJI: dict[str, str] = {
    "🔺": "highest",
    "⏫": "high",
    "🔼": "medium",
    "🔽": "low",
    "⏬": "lowest",
}
EMOJI_FOR_PRIORITY: dict[str, str] = {v: k for k, v in PRIORITY_EMOJI.items()}

_TODO_LINE_RE = re.compile(r"^\s*-\s+\[([ xX])\]\s+(.*)$")
_DUE_RE = re.compile(r"📅\s*(\d{4}-\d{2}-\d{2})")
_DONE_RE = re.compile(r"✅\s*(\d{4}-\d{2}-\d{2})")
_TAG_RE = re.compile(r"#([A-Za-z0-9_-]+)")
_MENTION_RE = re.compile(r"(?<![A-Za-z0-9_])@([A-Za-z0-9_-]+)")


@dataclass
class Todo:
    id: str
    raw: str
    done: bool
    text: str
    due: date | None = None
    priority: str | None = None
    tags: list[str] = field(default_factory=list)
    mentions: list[str] = field(default_factory=list)
    completed_at: date | None = None
    line_number: int = 0


def parse_todo_line(line: str, line_number: int = 0) -> Todo | None:
    m = _TODO_LINE_RE.match(line)
    if not m:
        return None
    done = m.group(1).lower() == "x"
    content = m.group(2).rstrip()

    due: date | None = None
    priority: str | None = None
    completed_at: date | None = None

    m_due = _DUE_RE.search(content)
    if m_due:
        try:
            due = date.fromisoformat(m_due.group(1))
            content = content[: m_due.start()] + content[m_due.end():]
        except ValueError:
            pass

    m_done = _DONE_RE.search(content)
    if m_done:
        try:
            completed_at = date.fromisoformat(m_done.group(1))
            content = content[: m_done.start()] + content[m_done.end():]
        except ValueError:
            pass

    for emoji, name in PRIORITY_EMOJI.items():
        if emoji in content:
            priority = name
            content = content.replace(emoji, "", 1)
            break

    tags = _TAG_RE.findall(content)
    mentions = _MENTION_RE.findall(content)

    # Strip tags and mentions from the text so the UI can render them as
    # separate badges / pills instead of inline noise.
    content = _TAG_RE.sub("", content)
    content = _MENTION_RE.sub("", content)

    text = re.sub(r"\s+", " ", content).strip()
    raw = line.rstrip("\n").rstrip()
    todo_id = hashlib.sha1(raw.encode()).hexdigest()[:12]

    return Todo(
        id=todo_id,
        raw=raw,
        done=done,
        text=text,
        due=due,
        priority=priority,
        tags=tags,
        mentions=mentions,
        completed_at=completed_at,
        line_number=line_number,
    )


def parse_todos(content: str) -> list[Todo]:
    out: list[Todo] = []
    for i, line in enumerate(content.splitlines()):
        t = parse_todo_line(line, i)
        if t is not None:
            out.append(t)
    return out


def serialize_todo(
    *,
    text: str,
    done: bool = False,
    due: date | None = None,
    priority: str | None = None,
    completed_at: date | None = None,
) -> str:
    parts: list[str] = [text.strip()]
    if priority and priority in EMOJI_FOR_PRIORITY:
        parts.append(EMOJI_FOR_PRIORITY[priority])
    if due:
        parts.append(f"📅 {due.isoformat()}")
    if completed_at and done:
        parts.append(f"✅ {completed_at.isoformat()}")
    body = " ".join(p for p in parts if p)
    box = "[x]" if done else "[ ]"
    return f"- {box} {body}"


def replace_todo_line(content: str, line_number: int, new_line: str) -> str:
    """Swap one line (0-indexed) in a multiline string.

    Preserves trailing newline behaviour — if the original content ended
    with a newline, the output does too.
    """
    trailing_nl = content.endswith("\n")
    lines = content.splitlines()
    if not 0 <= line_number < len(lines):
        raise IndexError(line_number)
    lines[line_number] = new_line
    out = "\n".join(lines)
    if trailing_nl:
        out += "\n"
    return out


def remove_todo_line(content: str, line_number: int) -> str:
    trailing_nl = content.endswith("\n")
    lines = content.splitlines()
    if not 0 <= line_number < len(lines):
        raise IndexError(line_number)
    del lines[line_number]
    out = "\n".join(lines)
    if trailing_nl:
        out += "\n"
    return out


def append_todo_line(content: str, new_line: str) -> str:
    """Append a todo line, ensuring it ends up on its own line with a
    trailing newline (so a subsequent append doesn't concatenate)."""
    if content and not content.endswith("\n"):
        content += "\n"
    return content + new_line + "\n"
