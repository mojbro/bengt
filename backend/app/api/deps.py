from fastapi import HTTPException, Request, status

from app.agent import AgentLoop
from app.config import Settings
from app.db import ConversationService
from app.indexer import Indexer
from app.llm import LLMProvider
from app.vault import VaultService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_vault(request: Request) -> VaultService:
    return request.app.state.vault


def get_indexer(request: Request) -> Indexer:
    return request.app.state.indexer


def get_conversations(request: Request) -> ConversationService:
    return request.app.state.conversations


def get_agent(request: Request) -> AgentLoop:
    return request.app.state.agent


def get_llm(request: Request) -> LLMProvider:
    return request.app.state.llm


def require_auth(request: Request) -> None:
    if not request.session.get("authed"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
        )
