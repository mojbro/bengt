import logging
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
from app.agent.web_tools import register_web_tools
from app.api import (
    audit as audit_api,
    auth,
    chat,
    conversations,
    scheduler as scheduler_api,
    vault,
)
from app.budget import BudgetService
from app.config import Settings
from app.config import settings as default_settings
from app.db import AuditService, ConversationService, NotFoundError
from app.db.models import Base
from app.indexer import Indexer
from app.llm import build_provider
from app.scheduler import create_scheduler
from app.scheduler_runner import (
    SchedulerServices,
    clear_services,
    register_services,
)
from app.vault import VaultService
from app.ws_manager import ConnectionManager

log = logging.getLogger(__name__)


def _load_or_create_session_secret(data_path: Path) -> str:
    secret_path = data_path / ".session_secret"
    if secret_path.exists():
        return secret_path.read_text().strip()
    secret = secrets.token_hex(32)
    secret_path.write_text(secret)
    return secret


def _ensure_scheduled_conversation(
    conv_service: ConversationService, data_path: Path
) -> str:
    """Find-or-create the dedicated thread for scheduled-job output.

    ID is persisted in `.scheduled_conversation_id` so restarts keep the
    same thread (and it survives user-driven renames of the conversation).
    """
    pointer = data_path / ".scheduled_conversation_id"
    if pointer.exists():
        existing_id = pointer.read_text().strip()
        try:
            conv_service.get(existing_id)
            return existing_id
        except NotFoundError:
            # Stale pointer (e.g., DB wiped); fall through to recreate.
            pass
    conv = conv_service.create(title="Scheduled")
    pointer.write_text(conv.id)
    return conv.id


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
        audit_service = AuditService(session_factory)
        budget = BudgetService(audit_service, cap_usd=s.daily_budget_usd)

        llm = build_provider(s)

        scheduler = create_scheduler()
        tools = ToolRegistry()
        register_vault_tools(tools, vault_svc, indexer)
        register_scheduler_tools(tools, scheduler)
        register_web_tools(tools)

        agent = AgentLoop(
            llm=llm,
            tools=tools,
            vault=vault_svc,
            audit=audit_service,
            budget=budget,
        )

        ws_manager = ConnectionManager()
        scheduled_conv_id: str | None = None

        # Only wire up the scheduler's runtime plumbing when it's actually
        # going to fire. Tests turn autostart off so they don't get a
        # surprise "Scheduled" conversation in their empty-list assertions.
        if s.scheduler_autostart:
            scheduled_conv_id = _ensure_scheduled_conversation(
                conv_service, data_path
            )
            register_services(
                SchedulerServices(
                    agent=agent,
                    conversations=conv_service,
                    ws_manager=ws_manager,
                    scheduled_conversation_id=scheduled_conv_id,
                )
            )
            scheduler.start()
            log.info("scheduler started")

        app.state.settings = s
        app.state.vault = vault_svc
        app.state.indexer = indexer
        app.state.llm = llm
        app.state.scheduler = scheduler
        app.state.tools = tools
        app.state.agent = agent
        app.state.db_engine = engine
        app.state.conversations = conv_service
        app.state.audit = audit_service
        app.state.budget = budget
        app.state.ws_manager = ws_manager
        app.state.scheduled_conversation_id = scheduled_conv_id  # may be None in tests

        try:
            yield
        finally:
            if scheduler.running:
                scheduler.shutdown(wait=False)
            clear_services()
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
    app.include_router(chat.router)
    app.include_router(scheduler_api.router)
    app.include_router(audit_api.router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "llm_provider": s.llm_provider}

    return app


app = create_app()
