"""Unit tests for the Obsidian Tasks parser/serializer."""

from datetime import date

from app.vault.todos import (
    append_todo_line,
    parse_todo_line,
    parse_todos,
    remove_todo_line,
    replace_todo_line,
    serialize_todo,
)


def test_parse_open_todo():
    t = parse_todo_line("- [ ] Call Volvo")
    assert t is not None
    assert t.done is False
    assert t.text == "Call Volvo"


def test_parse_closed_todo():
    t = parse_todo_line("- [x] Send invoice")
    assert t is not None
    assert t.done is True


def test_parse_due_date():
    t = parse_todo_line("- [ ] Call Volvo 📅 2026-04-25")
    assert t is not None
    assert t.due == date(2026, 4, 25)
    assert t.text == "Call Volvo"  # date stripped from text


def test_parse_priority():
    t = parse_todo_line("- [ ] Finish report 🔼")
    assert t is not None
    assert t.priority == "medium"
    assert "🔼" not in t.text


def test_parse_all_priorities():
    mapping = {
        "🔺": "highest",
        "⏫": "high",
        "🔼": "medium",
        "🔽": "low",
        "⏬": "lowest",
    }
    for emoji, name in mapping.items():
        t = parse_todo_line(f"- [ ] Task {emoji}")
        assert t is not None
        assert t.priority == name, f"{emoji} should be {name}"


def test_parse_tags_and_mentions():
    t = parse_todo_line("- [ ] Review doc #work @anna")
    assert t is not None
    assert t.tags == ["work"]
    assert t.mentions == ["anna"]


def test_parse_completed_date():
    t = parse_todo_line("- [x] Send invoice ✅ 2026-04-22")
    assert t is not None
    assert t.done is True
    assert t.completed_at == date(2026, 4, 22)


def test_parse_full_example():
    t = parse_todo_line("- [ ] Call Volvo about contract 📅 2026-04-25 🔼 #work @erik")
    assert t is not None
    assert t.text == "Call Volvo about contract"
    assert t.due == date(2026, 4, 25)
    assert t.priority == "medium"
    assert t.tags == ["work"]
    assert t.mentions == ["erik"]


def test_parse_non_todo_returns_none():
    assert parse_todo_line("# Todos") is None
    assert parse_todo_line("") is None
    assert parse_todo_line("- not a todo") is None


def test_parse_todos_skips_headings_and_blanks():
    content = """# Todos

- [ ] first
- [x] second

Some prose here.
- [ ] third 📅 2026-04-25
"""
    todos = parse_todos(content)
    assert len(todos) == 3
    assert [t.done for t in todos] == [False, True, False]


def test_parse_assigns_stable_ids():
    content = "- [ ] same text\n- [ ] other text"
    ids = [t.id for t in parse_todos(content)]
    assert len(set(ids)) == 2
    assert all(len(i) == 12 for i in ids)


def test_parse_tracks_line_numbers():
    content = "# Heading\n\n- [ ] first\n\n- [x] second"
    todos = parse_todos(content)
    assert todos[0].line_number == 2
    assert todos[1].line_number == 4


# -------------------- serializer


def test_serialize_minimal():
    assert serialize_todo(text="hi") == "- [ ] hi"


def test_serialize_with_done():
    assert serialize_todo(text="hi", done=True) == "- [x] hi"


def test_serialize_with_due():
    line = serialize_todo(text="Call", due=date(2026, 4, 25))
    assert line == "- [ ] Call 📅 2026-04-25"


def test_serialize_with_priority():
    line = serialize_todo(text="x", priority="high")
    assert "⏫" in line


def test_serialize_with_completion_only_when_done():
    assert (
        serialize_todo(text="x", done=True, completed_at=date(2026, 4, 22))
        == "- [x] x ✅ 2026-04-22"
    )
    # Completion date is omitted when done=False.
    assert (
        serialize_todo(text="x", done=False, completed_at=date(2026, 4, 22))
        == "- [ ] x"
    )


# -------------------- mutation helpers


def test_replace_todo_line_preserves_trailing_newline():
    original = "a\n- [ ] old\nc\n"
    updated = replace_todo_line(original, 1, "- [x] new")
    assert updated == "a\n- [x] new\nc\n"


def test_remove_todo_line():
    original = "a\n- [ ] drop me\nc\n"
    updated = remove_todo_line(original, 1)
    assert updated == "a\nc\n"


def test_append_todo_line_adds_newline_separator():
    original = "# Todos\n- [ ] one\n"
    updated = append_todo_line(original, "- [ ] two")
    assert updated == "# Todos\n- [ ] one\n- [ ] two\n"


def test_append_todo_line_handles_missing_final_newline():
    original = "# Todos"
    updated = append_todo_line(original, "- [ ] first")
    assert updated == "# Todos\n- [ ] first\n"
