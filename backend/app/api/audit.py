from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.api.deps import require_auth
from app.db import AuditService

router = APIRouter(
    prefix="/api/audit",
    tags=["audit"],
    dependencies=[Depends(require_auth)],
)


class AuditEntryOut(BaseModel):
    id: str
    timestamp: datetime
    kind: str
    conversation_id: str | None
    cost_usd: float
    data: dict[str, Any]


class BudgetStatusOut(BaseModel):
    cap_usd: float
    spent_usd: float
    remaining_usd: float
    exceeded: bool


def get_audit(request: Request) -> AuditService:
    return request.app.state.audit


def get_budget(request: Request):
    return request.app.state.budget


@router.get("/recent", response_model=list[AuditEntryOut])
def recent(
    limit: int = 100,
    conversation_id: str | None = None,
    audit: AuditService = Depends(get_audit),
) -> list[AuditEntryOut]:
    limit = max(1, min(limit, 500))
    return [
        AuditEntryOut(
            id=e.id,
            timestamp=e.timestamp,
            kind=e.kind,
            conversation_id=e.conversation_id,
            cost_usd=e.cost_usd,
            data=e.data or {},
        )
        for e in audit.recent(limit=limit, conversation_id=conversation_id)
    ]


@router.get("/budget", response_model=BudgetStatusOut)
def budget_status(budget=Depends(get_budget)) -> BudgetStatusOut:
    s = budget.status()
    return BudgetStatusOut(
        cap_usd=s.cap_usd,
        spent_usd=s.spent_usd,
        remaining_usd=s.remaining_usd,
        exceeded=s.exceeded,
    )
