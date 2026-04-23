"""REST API for managing todos.md structurally.

The markdown file remains the source of truth — these endpoints read, parse,
mutate, and write back. Lines are addressed by a stable content-hash id
(computed from the raw line); the frontend passes the id it last saw, and
the server re-parses to find the target. Simple, resilient to the agent
appending new todos between a list and a mutate call.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_vault, require_auth
from app.vault import NotFoundError, VaultService
from app.vault.todos import (
    Todo,
    append_todo_line,
    parse_todos,
    remove_todo_line,
    replace_todo_line,
    serialize_todo,
)

router = APIRouter(
    prefix="/api/todos",
    tags=["todos"],
    dependencies=[Depends(require_auth)],
)

TODOS_PATH = "todos.md"

PriorityLiteral = str  # "highest" | "high" | "medium" | "low" | "lowest" | None


class TodoOut(BaseModel):
    id: str
    text: str
    done: bool
    due: date | None
    priority: str | None
    tags: list[str]
    mentions: list[str]
    completed_at: date | None


class CreateTodoRequest(BaseModel):
    text: str = Field(min_length=1)
    due: date | None = None
    priority: str | None = None


class UpdateTodoRequest(BaseModel):
    text: str = Field(min_length=1)
    due: date | None = None
    priority: str | None = None


def _read_todos_content(vault: VaultService) -> str:
    try:
        return vault.read(TODOS_PATH)
    except NotFoundError:
        return "# Todos\n"


def _to_out(t: Todo) -> TodoOut:
    return TodoOut(
        id=t.id,
        text=t.text,
        done=t.done,
        due=t.due,
        priority=t.priority,
        tags=t.tags,
        mentions=t.mentions,
        completed_at=t.completed_at,
    )


def _find_by_id(vault: VaultService, todo_id: str) -> tuple[list[Todo], Todo, str]:
    """Returns (all_todos, target, full_file_content) or raises 404."""
    content = _read_todos_content(vault)
    todos = parse_todos(content)
    for t in todos:
        if t.id == todo_id:
            return todos, t, content
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"no todo {todo_id!r}")


@router.get("", response_model=list[TodoOut])
def list_todos(vault: VaultService = Depends(get_vault)) -> list[TodoOut]:
    content = _read_todos_content(vault)
    return [_to_out(t) for t in parse_todos(content)]


@router.post("", response_model=TodoOut, status_code=status.HTTP_201_CREATED)
def create_todo(
    body: CreateTodoRequest,
    vault: VaultService = Depends(get_vault),
) -> TodoOut:
    line = serialize_todo(
        text=body.text.strip(),
        done=False,
        due=body.due,
        priority=body.priority,
    )
    content = _read_todos_content(vault)
    new_content = append_todo_line(content, line)
    vault.write(TODOS_PATH, new_content, actor="user")
    # Re-parse and return the freshly created entry.
    for t in parse_todos(new_content):
        if t.raw.strip() == line.strip():
            return _to_out(t)
    # Fallback — shouldn't happen.
    raise HTTPException(500, "todo written but not found on re-read")


@router.post("/{todo_id}/toggle", response_model=TodoOut)
def toggle_todo(
    todo_id: str,
    vault: VaultService = Depends(get_vault),
) -> TodoOut:
    _, target, content = _find_by_id(vault, todo_id)
    new_done = not target.done
    completed_at = date.today() if new_done else None
    new_line = serialize_todo(
        text=target.text,
        done=new_done,
        due=target.due,
        priority=target.priority,
        completed_at=completed_at,
    )
    # Preserve existing tags/mentions by re-inserting them after the text.
    if target.tags or target.mentions:
        extras = " ".join(
            [f"#{t}" for t in target.tags] + [f"@{m}" for m in target.mentions]
        )
        # Inject extras right after the text segment, before the metadata.
        # Simpler: rebuild starting from text + extras as the "text" input.
        new_line = serialize_todo(
            text=f"{target.text} {extras}".strip(),
            done=new_done,
            due=target.due,
            priority=target.priority,
            completed_at=completed_at,
        )
    new_content = replace_todo_line(content, target.line_number, new_line)
    vault.write(TODOS_PATH, new_content, actor="user")
    for t in parse_todos(new_content):
        if t.line_number == target.line_number:
            return _to_out(t)
    raise HTTPException(500, "toggle write succeeded but re-parse failed")


@router.patch("/{todo_id}", response_model=TodoOut)
def update_todo(
    todo_id: str,
    body: UpdateTodoRequest,
    vault: VaultService = Depends(get_vault),
) -> TodoOut:
    _, target, content = _find_by_id(vault, todo_id)
    # Keep the existing tags/mentions if the user included them in the new
    # text; if not, the ones they had are gone. Simpler UX than trying to
    # merge; the edit form exposes text as a single field so the user sees
    # exactly what's there.
    new_line = serialize_todo(
        text=body.text.strip(),
        done=target.done,
        due=body.due,
        priority=body.priority,
        completed_at=target.completed_at,
    )
    new_content = replace_todo_line(content, target.line_number, new_line)
    vault.write(TODOS_PATH, new_content, actor="user")
    for t in parse_todos(new_content):
        if t.line_number == target.line_number:
            return _to_out(t)
    raise HTTPException(500, "update write succeeded but re-parse failed")


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(
    todo_id: str,
    vault: VaultService = Depends(get_vault),
) -> None:
    _, target, content = _find_by_id(vault, todo_id)
    new_content = remove_todo_line(content, target.line_number)
    vault.write(TODOS_PATH, new_content, actor="user")
