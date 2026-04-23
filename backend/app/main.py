from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.config import settings
from app.vault import VaultService


@asynccontextmanager
async def lifespan(app: FastAPI):
    vault = VaultService(Path(settings.vault_path))
    vault.bootstrap()
    app.state.vault = vault
    yield


app = FastAPI(title="bengt", version="0.1.0", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "llm_provider": settings.llm_provider}
