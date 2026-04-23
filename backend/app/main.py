from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.agent import AgentLoop, ToolRegistry, register_mock_tools
from app.config import settings
from app.indexer import Indexer
from app.llm import build_provider
from app.vault import VaultService


@asynccontextmanager
async def lifespan(app: FastAPI):
    indexer = Indexer(db_path=Path(settings.data_path) / "chroma")
    vault = VaultService(Path(settings.vault_path), indexer=indexer)
    vault.bootstrap()
    indexer.reindex_all(vault.root)

    llm = build_provider(settings)
    tools = ToolRegistry()
    register_mock_tools(tools)  # step 5: mocks only; real tools land in step 6
    agent = AgentLoop(llm=llm, tools=tools, vault=vault)

    app.state.vault = vault
    app.state.indexer = indexer
    app.state.llm = llm
    app.state.tools = tools
    app.state.agent = agent
    yield


app = FastAPI(title="bengt", version="0.1.0", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "llm_provider": settings.llm_provider}
