from pathlib import Path

import pytest
from git import Repo

from app.vault import EditError, NotFoundError, PathSafetyError, VaultService


def test_bootstrap_creates_repo_and_stubs(vault_root: Path):
    svc = VaultService(vault_root)
    svc.bootstrap()
    assert (vault_root / ".git").is_dir()
    for name in ("todos.md", "memory.md", "preferences.md"):
        assert (vault_root / name).exists()
    repo = Repo(vault_root)
    assert len(list(repo.iter_commits())) == 3


def test_bootstrap_is_idempotent(vault: VaultService):
    repo = Repo(vault.root)
    before = len(list(repo.iter_commits()))
    vault.bootstrap()
    after = len(list(repo.iter_commits()))
    assert before == after


def test_bootstrap_preserves_existing_files(vault_root: Path):
    vault_root.mkdir(parents=True)
    (vault_root / "memory.md").write_text("# existing content\n")
    svc = VaultService(vault_root)
    svc.bootstrap()
    assert (vault_root / "memory.md").read_text() == "# existing content\n"


def test_write_creates_file_and_commits(vault: VaultService):
    vault.write("notes/hello.md", "hi there\n", actor="user")
    assert (vault.root / "notes/hello.md").read_text() == "hi there\n"
    latest = next(Repo(vault.root).iter_commits())
    assert "user: write notes/hello.md" in latest.message
    assert latest.author.name == "user"


def test_agent_author_on_commit(vault: VaultService):
    vault.write("notes/agent.md", "by the agent\n", actor="agent")
    latest = next(Repo(vault.root).iter_commits())
    assert latest.author.name == "agent"
    assert "agent: write notes/agent.md" in latest.message


def test_edit_replaces_unique_occurrence(vault: VaultService):
    vault.write("todos.md", "# Todos\n- [ ] buy milk\n", actor="user")
    vault.edit("todos.md", "buy milk", "buy oat milk", actor="agent")
    assert "buy oat milk" in (vault.root / "todos.md").read_text()


def test_edit_fails_on_multiple_occurrences(vault: VaultService):
    vault.write("todos.md", "foo\nfoo\n", actor="user")
    with pytest.raises(EditError):
        vault.edit("todos.md", "foo", "bar")


def test_edit_fails_on_missing_string(vault: VaultService):
    with pytest.raises(EditError):
        vault.edit("todos.md", "not present", "whatever")


def test_edit_fails_on_missing_file(vault: VaultService):
    with pytest.raises(NotFoundError):
        vault.edit("does-not-exist.md", "a", "b")


def test_append(vault: VaultService):
    before = (vault.root / "todos.md").read_text()
    vault.append("todos.md", "- [ ] new item\n", actor="user")
    assert (vault.root / "todos.md").read_text() == before + "- [ ] new item\n"


def test_read_missing_raises(vault: VaultService):
    with pytest.raises(NotFoundError):
        vault.read("nonexistent.md")


def test_list_root(vault: VaultService):
    names = {e.path for e in vault.list()}
    assert {"todos.md", "memory.md", "preferences.md"}.issubset(names)
    assert ".git" not in names


def test_list_subdirectory(vault: VaultService):
    vault.write("notes/a.md", "a\n")
    vault.write("notes/b.md", "b\n")
    names = {e.path for e in vault.list("notes")}
    assert names == {"notes/a.md", "notes/b.md"}


def test_path_safety_in_write(vault: VaultService):
    with pytest.raises(PathSafetyError):
        vault.write("../escape.md", "x")


def test_delete_removes_file_and_commits(vault: VaultService):
    vault.write("notes/doomed.md", "goodbye\n", actor="user")
    assert (vault.root / "notes/doomed.md").exists()

    vault.delete("notes/doomed.md", actor="user")
    assert not (vault.root / "notes/doomed.md").exists()

    latest = next(Repo(vault.root).iter_commits())
    assert "user: delete notes/doomed.md" in latest.message
    assert latest.author.name == "user"


def test_delete_missing_raises(vault: VaultService):
    with pytest.raises(NotFoundError):
        vault.delete("notes/never-existed.md")


def test_delete_path_safety(vault: VaultService):
    with pytest.raises(PathSafetyError):
        vault.delete("../outside.md")


def test_delete_removes_from_index(indexed_vault: VaultService, indexer):
    indexed_vault.write("notes/searchable.md", "unique phrase xyz", actor="user")
    hits = indexer.search("unique phrase xyz")
    assert any(h.path == "notes/searchable.md" for h in hits)

    indexed_vault.delete("notes/searchable.md")
    hits = indexer.search("unique phrase xyz")
    assert all(h.path != "notes/searchable.md" for h in hits)
