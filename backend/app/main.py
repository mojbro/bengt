import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from app.agent import AgentLoop, ToolRegistry
from app.agent.scheduler_tools import register_scheduler_tools
from app.agent.vault_tools import register_vault_tools
from app.api import auth, conversations, vault
from app.config import Settings
from app.config import settings as default_settings
from app.db import ConversationService
from app.db.models import Base
from app.indexer import Indexer
from app.llm import build_provider
from app.scheduler import create_scheduler
from app.vault import VaultService


def _load_or_create_session_secret(data_path: Path) -> str:
    secret_path = data_path / ".session_secret"
    if secret_path.exists():
        return secret_path.read_text().strip()
    secret = secrets.token_hex(32)
    secret_path.write_text(secret)
    return secret


def create_app(settings: Settings | None = None) -> FastAPI:
    s = settings or default_settings

    data_path = Path(s.data_path)
    data_path.mkdir(parents=True, exist_ok=True)
    session_secret = _load_or_create_session_secret(data_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        indexer = Indexer(db_path=data_path / "chroma")
        vault_svc = VaultService(Path(s.vault_path), indexer=indexer)
        vault_svc.bootstrap()
        indexer.reindex_all(vault_svc.root)

        engine = create_engine(f"sqlite:///{data_path / 'app.db'}")
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        conv_service = ConversationService(session_factory)

        llm = build_provider(s)

        scheduler = create_scheduler()
        # scheduler is intentionally not started; step 14 starts it.

        tools = ToolRegistry()
        register_vault_tools(tools, vault_svc, indexer)
        register_scheduler_tools(tools, scheduler)

        agent = AgentLoop(llm=llm, tools=tools, vault=vault_svc)

        app.state.settings = s
        app.state.vault = vault_svc
        app.state.indexer = indexer
        app.state.llm = llm
        app.state.scheduler = scheduler
        app.state.tools = tools
        app.state.agent = agent
        app.state.db_engine = engine
        app.state.conversations = conv_service

        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="bengt", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        https_only=False,
        same_site="lax",
    )
    app.include_router(auth.router)
    app.include_router(vault.router)
    app.include_router(conversations.router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "llm_provider": s.llm_provider}

    return app


app = create_app()
