from pathlib import Path

from app.indexer import Indexer
from app.vault import VaultService


def test_upsert_and_search(tmp_path: Path):
    indexer = Indexer(db_path=tmp_path / "chroma")
    indexer.upsert("notes/meeting.md", "Meeting with Volvo tomorrow at 10am about the contract")
    indexer.upsert("notes/shopping.md", "Buy milk, eggs, and bread")
    hits = indexer.search("when is the Volvo meeting", limit=1)
    assert len(hits) == 1
    assert hits[0].path == "notes/meeting.md"


def test_upsert_replaces_existing_content(tmp_path: Path):
    indexer = Indexer(db_path=tmp_path / "chroma")
    indexer.upsert("note.md", "apples are red")
    indexer.upsert("note.md", "bananas are yellow")
    assert indexer.count() == 1
    hits = indexer.search("what color is the banana", limit=1)
    assert hits and hits[0].path == "note.md"
    assert "banana" in hits[0].snippet


def test_remove(tmp_path: Path):
    indexer = Indexer(db_path=tmp_path / "chroma")
    indexer.upsert("a.md", "hello world")
    indexer.upsert("b.md", "foo bar")
    indexer.remove("a.md")
    assert indexer.count() == 1
    hits = indexer.search("hello", limit=5)
    assert all(h.path != "a.md" for h in hits)


def test_empty_content_is_not_indexed(tmp_path: Path):
    indexer = Indexer(db_path=tmp_path / "chroma")
    indexer.upsert("empty.md", "")
    assert indexer.count() == 0


def test_search_on_empty_index_returns_empty(tmp_path: Path):
    indexer = Indexer(db_path=tmp_path / "chroma")
    assert indexer.search("anything") == []


def test_reindex_all_only_markdown(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "a.md").write_text("apple")
    (vault / "b.txt").write_text("not markdown, skipped")
    sub = vault / "sub"
    sub.mkdir()
    (sub / "c.md").write_text("cherry")
    indexer = Indexer(db_path=tmp_path / "chroma")
    indexer.reindex_all(vault)
    assert indexer.count() == 2


def test_vault_write_indexes_file(indexed_vault: VaultService, indexer: Indexer):
    indexed_vault.write("notes/volvo.md", "Meeting tomorrow about the Volvo contract renewal")
    hits = indexer.search("Volvo contract")
    assert any(h.path == "notes/volvo.md" for h in hits)


def test_vault_edit_updates_index(indexed_vault: VaultService, indexer: Indexer):
    indexed_vault.write("notes/task.md", "buy milk today at the store")
    indexed_vault.edit("notes/task.md", "buy milk", "buy oat milk")
    hits = indexer.search("oat milk groceries", limit=1)
    assert hits and hits[0].path == "notes/task.md"
    assert "oat milk" in hits[0].snippet


def test_vault_without_indexer_still_works(vault: VaultService):
    # Sanity: VaultService with indexer=None (the existing `vault` fixture)
    # should still write/edit files without errors.
    vault.write("notes/plain.md", "no index attached")
    assert (vault.root / "notes/plain.md").read_text() == "no index attached"
