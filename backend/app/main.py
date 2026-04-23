from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.agent import AgentLoop, ToolRegistry
from app.agent.scheduler_tools import register_scheduler_tools
from app.agent.vault_tools import register_vault_tools
from app.config import settings
from app.indexer import Indexer
from app.llm import build_provider
from app.scheduler import create_scheduler
from app.vault import VaultService


@asynccontextmanager
async def lifespan(app: FastAPI):
    indexer = Indexer(db_path=Path(settings.data_path) / "chroma")
    vault = VaultService(Path(settings.vault_path), indexer=indexer)
    vault.bootstrap()
    indexer.reindex_all(vault.root)

    llm = build_provider(settings)

    scheduler = create_scheduler()
    # NOTE: scheduler is NOT started in step 6. Jobs added by the agent are
    # stored and listable, but won't fire until step 14 starts it and wires
    # job_fire_placeholder to real agent invocation.

    tools = ToolRegistry()
    register_vault_tools(tools, vault, indexer)
    register_scheduler_tools(tools, scheduler)

    agent = AgentLoop(llm=llm, tools=tools, vault=vault)

    app.state.vault = vault
    app.state.indexer = indexer
    app.state.llm = llm
    app.state.scheduler = scheduler
    app.state.tools = tools
    app.state.agent = agent
    yield


app = FastAPI(title="bengt", version="0.1.0", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "llm_provider": settings.llm_provider}
