from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent import AgentLoop, ToolRegistry
from app.agent.scheduler_tools import register_scheduler_tools
from app.agent.vault_tools import register_vault_tools
from app.config import settings
from app.db import ConversationService
from app.db.models import Base
from app.indexer import Indexer
from app.llm import build_provider
from app.scheduler import create_scheduler
from app.vault import VaultService


@asynccontextmanager
async def lifespan(app: FastAPI):
    data_path = Path(settings.data_path)
    data_path.mkdir(parents=True, exist_ok=True)

    indexer = Indexer(db_path=data_path / "chroma")
    vault = VaultService(Path(settings.vault_path), indexer=indexer)
    vault.bootstrap()
    indexer.reindex_all(vault.root)

    engine = create_engine(f"sqlite:///{data_path / 'app.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    conversations = ConversationService(session_factory)

    llm = build_provider(settings)

    scheduler = create_scheduler()
    # scheduler is intentionally not started in step 6/7; step 14 starts it.

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
    app.state.db_engine = engine
    app.state.conversations = conversations

    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(title="bengt", version="0.1.0", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "llm_provider": settings.llm_provider}
