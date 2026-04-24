import sqlite3
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import ForeignKey, JSON, Text, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(default="New thread")
    # Configured model name (a key from Settings.llm_models). NULL means
    # "use the default"; the existence of the column is handled by a
    # small inline migration in app.main so old databases upgrade cleanly.
    model: Mapped[str | None] = mapped_column(default=None, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.sequence",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int]
    role: Mapped[str]
    content: Mapped[str] = mapped_column(Text, default="")
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    tool_call_id: Mapped[str | None] = mapped_column(nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class AuditEntry(Base):
    """One row per LLM call or tool invocation.

    The `data` JSON blob holds kind-specific fields (model/tokens for LLM
    calls, name/arguments/result_preview for tools) so we can grow the
    schema without migrations.
    """

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(default=_now, index=True)
    kind: Mapped[str]  # "llm_call" | "tool_invocation"
    conversation_id: Mapped[str | None] = mapped_column(default=None)
    cost_usd: Mapped[float] = mapped_column(default=0.0)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


# SQLite needs this pragma each connection for ON DELETE CASCADE to fire.
@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
