from git import Repo

from app.agent import ToolRegistry
from app.agent.vault_tools import register_vault_tools
from app.indexer import Indexer
from app.vault import VaultService


def _registry(vault: VaultService, indexer: Indexer) -> ToolRegistry:
    reg = ToolRegistry()
    register_vault_tools(reg, vault, indexer)
    return reg


async def test_all_vault_tools_registered(indexed_vault, indexer):
    reg = _registry(indexed_vault, indexer)
    assert set(reg.names()) == {
        "search_vault",
        "list_vault",
        "read_file",
        "write_file",
        "edit_file",
        "append_to_file",
    }


async def test_search_vault_returns_hits(indexed_vault, indexer):
    reg = _registry(indexed_vault, indexer)
    indexed_vault.write(
        "notes/volvo.md",
        "Meeting with Volvo on Friday at 10am about contract renewal.",
        actor="user",
    )
    out = await reg.invoke("search_vault", {"query": "Volvo meeting"})
    assert "notes/volvo.md" in out
    assert "Volvo" in out


async def test_search_vault_empty(indexer, tmp_path):
    # Fresh vault without bootstrap → nothing indexed.
    vault = VaultService(tmp_path / "blank")
    (tmp_path / "blank").mkdir()
    reg = _registry(vault, indexer)
    out = await reg.invoke("search_vault", {"query": "anything"})
    assert out == "(no results)"


async def test_list_vault_root(indexed_vault, indexer):
    reg = _registry(indexed_vault, indexer)
    out = await reg.invoke("list_vault", {})
    for expected in ("todos.md", "memory.md", "preferences.md"):
        assert expected in out


async def test_list_vault_subpath(indexed_vault, indexer):
    indexed_vault.write("notes/a.md", "a")
    indexed_vault.write("notes/b.md", "b")
    reg = _registry(indexed_vault, indexer)
    out = await reg.invoke("list_vault", {"path": "notes"})
    assert "notes/a.md" in out and "notes/b.md" in out


async def test_read_file(indexed_vault, indexer):
    reg = _registry(indexed_vault, indexer)
    content = await reg.invoke("read_file", {"path": "todos.md"})
    assert content.startswith("# Todos")


async def test_write_file_commits_as_agent(indexed_vault, indexer):
    reg = _registry(indexed_vault, indexer)
    out = await reg.invoke(
        "write_file", {"path": "notes/reminder.md", "content": "call Dad"}
    )
    assert "notes/reminder.md" in out
    assert (indexed_vault.root / "notes/reminder.md").read_text() == "call Dad"

    latest = next(Repo(indexed_vault.root).iter_commits())
    assert latest.author.name == "agent"
    assert "agent: write notes/reminder.md" in latest.message


async def test_edit_file_commits_as_agent(indexed_vault, indexer):
    indexed_vault.write("notes/task.md", "buy milk today", actor="user")
    reg = _registry(indexed_vault, indexer)
    await reg.invoke(
        "edit_file",
        {
            "path": "notes/task.md",
            "old_string": "buy milk",
            "new_string": "buy oat milk",
        },
    )
    assert "oat milk" in (indexed_vault.root / "notes/task.md").read_text()
    latest = next(Repo(indexed_vault.root).iter_commits())
    assert latest.author.name == "agent"


async def test_append_to_file(indexed_vault, indexer):
    reg = _registry(indexed_vault, indexer)
    before = (indexed_vault.root / "todos.md").read_text()
    await reg.invoke(
        "append_to_file",
        {"path": "todos.md", "content": "- [ ] new item\n"},
    )
    after = (indexed_vault.root / "todos.md").read_text()
    assert after == before + "- [ ] new item\n"


async def test_path_safety_rejects_traversal(indexed_vault, indexer):
    from app.vault.paths import PathSafetyError
    import pytest

    reg = _registry(indexed_vault, indexer)
    with pytest.raises(PathSafetyError):
        await reg.invoke(
            "write_file",
            {"path": "../escaped.md", "content": "nope"},
        )
