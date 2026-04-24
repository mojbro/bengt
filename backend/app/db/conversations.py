import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Conversation, Message
from app.llm import Message as LLMMessage
from app.llm import ToolCall


class NotFoundError(Exception):
    """Raised when a conversation lookup fails."""


class ConversationService:
    """Sync CRUD + message log for chat threads.

    FastAPI runs sync endpoints in a thread pool, so DB calls don't block the
    event loop — async SQLAlchemy isn't worth the complexity at MVP scale.
    """

    def __init__(self, session_factory: sessionmaker[Session]):
        self._factory = session_factory

    # -------------------- conversations

    def create(
        self, title: str = "New thread", model: str | None = None
    ) -> Conversation:
        with self._factory() as session:
            conv = Conversation(id=str(uuid.uuid4()), title=title, model=model)
            session.add(conv)
            session.commit()
            session.refresh(conv)
            return conv

    def recent(self, limit: int = 50) -> list[Conversation]:
        with self._factory() as session:
            rows = session.execute(
                select(Conversation)
                .order_by(Conversation.updated_at.desc())
                .limit(limit)
            ).scalars().all()
            return list(rows)

    def get(self, conv_id: str) -> Conversation:
        with self._factory() as session:
            conv = session.get(Conversation, conv_id)
            if conv is None:
                raise NotFoundError(f"conversation {conv_id!r} not found")
            return conv

    def rename(self, conv_id: str, title: str) -> None:
        with self._factory() as session:
            conv = session.get(Conversation, conv_id)
            if conv is None:
                raise NotFoundError(f"conversation {conv_id!r} not found")
            conv.title = title
            conv.updated_at = datetime.now(timezone.utc)
            session.commit()

    def set_model(self, conv_id: str, model: str | None) -> None:
        """Assign (or clear) the model for a conversation."""
        with self._factory() as session:
            conv = session.get(Conversation, conv_id)
            if conv is None:
                raise NotFoundError(f"conversation {conv_id!r} not found")
            conv.model = model
            conv.updated_at = datetime.now(timezone.utc)
            session.commit()

    def delete(self, conv_id: str) -> None:
        with self._factory() as session:
            conv = session.get(Conversation, conv_id)
            if conv is None:
                raise NotFoundError(f"conversation {conv_id!r} not found")
            session.delete(conv)
            session.commit()

    # -------------------- messages

    def append_message(
        self,
        conv_id: str,
        role: str,
        content: str = "",
        tool_calls: list[ToolCall] | None = None,
        tool_call_id: str | None = None,
    ) -> Message:
        with self._factory() as session:
            conv = session.get(Conversation, conv_id)
            if conv is None:
                raise NotFoundError(f"conversation {conv_id!r} not found")

            max_seq = session.execute(
                select(func.coalesce(func.max(Message.sequence), 0)).where(
                    Message.conversation_id == conv_id
                )
            ).scalar_one()

            serialized_tool_calls: list[dict[str, object]] | None = None
            if tool_calls:
                serialized_tool_calls = [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in tool_calls
                ]

            msg = Message(
                id=str(uuid.uuid4()),
                conversation_id=conv_id,
                sequence=max_seq + 1,
                role=role,
                content=content,
                tool_calls=serialized_tool_calls,
                tool_call_id=tool_call_id,
            )
            session.add(msg)
            conv.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(msg)
            return msg

    def messages(self, conv_id: str) -> list[Message]:
        with self._factory() as session:
            rows = session.execute(
                select(Message)
                .where(Message.conversation_id == conv_id)
                .order_by(Message.sequence.asc())
            ).scalars().all()
            return list(rows)

    def to_llm_messages(self, conv_id: str) -> list[LLMMessage]:
        """Shape DB rows for feeding back into AgentLoop.run(history=...)."""
        return [self._to_llm(m) for m in self.messages(conv_id)]

    @staticmethod
    def _to_llm(msg: Message) -> LLMMessage:
        tool_calls = [
            ToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
            for tc in (msg.tool_calls or [])
        ]
        return LLMMessage(
            role=msg.role,  # type: ignore[arg-type]
            content=msg.content or "",
            tool_calls=tool_calls,
            tool_call_id=msg.tool_call_id or "",
        )
