from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.config import settings
from app.indexer import Indexer
from app.vault import VaultService


@asynccontextmanager
async def lifespan(app: FastAPI):
    indexer = Indexer(db_path=Path(settings.data_path) / "chroma")
    vault = VaultService(Path(settings.vault_path), indexer=indexer)
    vault.bootstrap()
    indexer.reindex_all(vault.root)
    app.state.vault = vault
    app.state.indexer = indexer
    yield


app = FastAPI(title="bengt", version="0.1.0", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "llm_provider": settings.llm_provider}
