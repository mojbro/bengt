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
    model: str | None
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
    model: str | None = None


class PatchRequest(BaseModel):
    """All fields optional — only the ones present get applied."""

    title: str | None = None
    # `model` uses an explicit sentinel (not-present vs null) via
    # Pydantic's model_fields_set. Clients that want to clear the model
    # and fall back to the default should send {"model": null}; clients
    # that want to leave it alone should omit the field.
    model: str | None = None


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
    return _conv_to_out(service.create(title=body.title, model=body.model))


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
        model=conv.model,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[_msg_to_out(m) for m in msgs],
    )


@router.patch("/{conv_id}", response_model=ConversationOut)
def patch_conversation(
    conv_id: str,
    body: PatchRequest,
    service: ConversationService = Depends(get_conversations),
) -> ConversationOut:
    try:
        fields_set = body.model_fields_set
        if "title" in fields_set and body.title is not None:
            service.rename(conv_id, body.title)
        if "model" in fields_set:
            service.set_model(conv_id, body.model)
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
        model=conv.model,
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
