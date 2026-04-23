from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings


@dataclass(frozen=True)
class SearchHit:
    path: str
    snippet: str
    distance: float


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
        self._collection.upsert(
            ids=[path],
            documents=[content],
            metadatas=[{"path": path}],
        )

    def remove(self, path: str) -> None:
        self._collection.delete(ids=[path])

    def search(self, query: str, limit: int = 5) -> list[SearchHit]:
        if limit <= 0 or self._collection.count() == 0:
            return []
        results = self._collection.query(
            query_texts=[query],
            n_results=min(limit, self._collection.count()),
        )
        ids = (results.get("ids") or [[]])[0]
        docs = (results.get("documents") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]
        hits: list[SearchHit] = []
        for doc_id, doc, dist in zip(ids, docs, distances):
            snippet = (doc or "")[:200]
            hits.append(SearchHit(path=doc_id, snippet=snippet, distance=float(dist)))
        return hits

    def reindex_all(self, vault_root: Path) -> None:
        vault_root = Path(vault_root)
        for path in sorted(vault_root.rglob("*.md")):
            rel = path.relative_to(vault_root).as_posix()
            self.upsert(rel, path.read_text())

    def count(self) -> int:
        return self._collection.count()
