from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings


@dataclass(frozen=True)
class SearchHit:
    path: str
    snippet: str
    distance: float


# Chunk large .md files before embedding. Paragraphs are the natural unit;
# we greedily group paragraphs up to MAX_CHUNK_CHARS so small notes stay
# one chunk and large docs (uploaded PDFs etc.) are searchable paragraph
# by paragraph.
MAX_CHUNK_CHARS = 1500


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        p = paragraph.strip()
        if not p:
            continue
        if not current:
            current = p
            continue
        if len(current) + len(p) + 2 > max_chars:
            chunks.append(current)
            current = p
        else:
            current = f"{current}\n\n{p}"
    if current:
        chunks.append(current)
    return chunks


class Indexer:
    def __init__(self, db_path: Path, collection_name: str = "vault"):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(name=collection_name)

    def upsert(self, path: str, content: str) -> None:
        if not content.strip():
            self.remove(path)
            return
        chunks = chunk_text(content)
        if not chunks:
            self.remove(path)
            return
        # Drop any previous chunks for this path. Delete by metadata so the
        # old chunk count doesn't have to match the new one.
        self._delete_by_path(path)
        ids = [f"{path}#{i}" for i in range(len(chunks))]
        metadatas = [{"path": path, "chunk": i} for i in range(len(chunks))]
        self._collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)

    def remove(self, path: str) -> None:
        self._delete_by_path(path)

    def _delete_by_path(self, path: str) -> None:
        # Chroma expects a dict-ish where clause.
        self._collection.delete(where={"path": path})

    def search(self, query: str, limit: int = 5) -> list[SearchHit]:
        if limit <= 0 or self._collection.count() == 0:
            return []
        results = self._collection.query(
            query_texts=[query],
            n_results=min(limit, self._collection.count()),
        )
        docs = (results.get("documents") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        hits: list[SearchHit] = []
        for doc, dist, meta in zip(docs, distances, metadatas):
            path = str((meta or {}).get("path", ""))
            snippet = (doc or "")[:200]
            hits.append(SearchHit(path=path, snippet=snippet, distance=float(dist)))
        return hits

    def reindex_all(self, vault_root: Path) -> None:
        vault_root = Path(vault_root)
        for path in sorted(vault_root.rglob("*.md")):
            rel = path.relative_to(vault_root).as_posix()
            self.upsert(rel, path.read_text())

    def count(self) -> int:
        return self._collection.count()
