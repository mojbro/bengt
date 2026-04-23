"""Audit log service — one row per LLM call or tool invocation.

Per PRD §7.3, every agent decision is auditable. `cost_today_utc` is the
aggregate the BudgetService queries for enforcement.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import AuditEntry


def _truncate(value: Any, limit: int = 200) -> Any:
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + f"… ({len(value)} chars)"
    return value


def _truncate_dict(d: dict[str, Any], limit: int = 200) -> dict[str, Any]:
    return {k: _truncate(v, limit) for k, v in d.items()}


class AuditService:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._factory = session_factory

    def record_llm_call(
        self,
        *,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float | None,
        conversation_id: str | None = None,
    ) -> AuditEntry:
        with self._factory() as session:
            entry = AuditEntry(
                id=str(uuid.uuid4()),
                kind="llm_call",
                conversation_id=conversation_id,
                cost_usd=float(cost_usd) if cost_usd is not None else 0.0,
                data={
                    "provider": provider,
                    "model": model,
                    "input_tokens": int(input_tokens),
                    "output_tokens": int(output_tokens),
                    "cost_usd": cost_usd,
                },
            )
            session.add(entry)
            session.commit()
            session.refresh(entry)
            return entry

    def record_tool_invocation(
        self,
        *,
        name: str,
        arguments: dict[str, Any],
        result: str,
        error: bool,
        conversation_id: str | None = None,
    ) -> AuditEntry:
        with self._factory() as session:
            entry = AuditEntry(
                id=str(uuid.uuid4()),
                kind="tool_invocation",
                conversation_id=conversation_id,
                cost_usd=0.0,
                data={
                    "name": name,
                    "arguments": _truncate_dict(arguments),
                    "result_preview": _truncate(result or "", 400),
                    "error": error,
                },
            )
            session.add(entry)
            session.commit()
            session.refresh(entry)
            return entry

    def recent(self, limit: int = 100) -> list[AuditEntry]:
        with self._factory() as session:
            rows = session.execute(
                select(AuditEntry)
                .order_by(AuditEntry.timestamp.desc())
                .limit(limit)
            ).scalars().all()
            return list(rows)

    def cost_today_utc(self) -> float:
        start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        with self._factory() as session:
            total = session.execute(
                select(func.coalesce(func.sum(AuditEntry.cost_usd), 0.0)).where(
                    AuditEntry.timestamp >= start
                )
            ).scalar_one()
            return float(total or 0.0)
