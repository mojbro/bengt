from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_conversations, require_auth
from app.db import ConversationService, NotFoundError

router = APIRouter(
    prefix="/api/conversations",
    tags=["conversations"],
    dependencies=[Depends(require_auth)],
)


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: str
    sequence: int
    role: str
    content: str
    tool_calls: list[dict[str, Any]] | None
    tool_call_id: str | None
    created_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class CreateRequest(BaseModel):
    title: str = "New thread"


class RenameRequest(BaseModel):
    title: str


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    service: ConversationService = Depends(get_conversations),
) -> list[ConversationOut]:
    return [_conv_to_out(c) for c in service.recent()]


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    body: CreateRequest,
    service: ConversationService = Depends(get_conversations),
) -> ConversationOut:
    return _conv_to_out(service.create(title=body.title))


@router.get("/{conv_id}", response_model=ConversationDetail)
def get_conversation(
    conv_id: str,
    service: ConversationService = Depends(get_conversations),
) -> ConversationDetail:
    try:
        conv = service.get(conv_id)
        msgs = service.messages(conv_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[_msg_to_out(m) for m in msgs],
    )


@router.patch("/{conv_id}", response_model=ConversationOut)
def rename_conversation(
    conv_id: str,
    body: RenameRequest,
    service: ConversationService = Depends(get_conversations),
) -> ConversationOut:
    try:
        service.rename(conv_id, body.title)
        return _conv_to_out(service.get(conv_id))
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conv_id: str,
    service: ConversationService = Depends(get_conversations),
) -> None:
    try:
        service.delete(conv_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


def _conv_to_out(conv) -> ConversationOut:
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


def _msg_to_out(msg) -> MessageOut:
    return MessageOut(
        id=msg.id,
        sequence=msg.sequence,
        role=msg.role,
        content=msg.content,
        tool_calls=msg.tool_calls,
        tool_call_id=msg.tool_call_id,
        created_at=msg.created_at,
    )
