"""POST /api/uploads — accept a document, save original + markdown, summarise."""

from __future__ import annotations

import mimetypes
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import get_vault, require_auth
from app.uploads import (
    AuthRequiredError,
    FileTooLargeError,
    UnsupportedFileTypeError,
    fetch_url_as_upload,
    handle_upload,
    open_vault_file_for_stream,
)
from app.vault import NotFoundError, PathSafetyError, VaultError, VaultService

router = APIRouter(
    prefix="/api/uploads",
    tags=["uploads"],
    dependencies=[Depends(require_auth)],
)


class UploadOut(BaseModel):
    original_path: str
    md_path: str
    summary: str
    tags: list[str]
    extracted_chars: int


class FromUrlRequest(BaseModel):
    url: str
    conversation_id: str | None = None


@router.post("", response_model=UploadOut, status_code=status.HTTP_201_CREATED)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    conversation_id: str | None = Form(default=None),
    vault: VaultService = Depends(get_vault),
) -> UploadOut:
    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty upload.")

    # Size sanity before text extraction — 30MB hard cap on raw bytes so we
    # don't get stuck parsing a huge binary.
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File too large ({len(data):,} bytes).",
        )

    llm = request.app.state.llm
    audit = getattr(request.app.state, "audit", None)

    try:
        result = await handle_upload(
            file_bytes=data,
            filename=file.filename or "file",
            content_type=file.content_type or "",
            vault=vault,
            llm=llm,
            audit=audit,
            conversation_id=conversation_id,
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    except FileTooLargeError as exc:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc)
        ) from exc
    except PathSafetyError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    return UploadOut(
        original_path=result.original_path,
        md_path=result.md_path,
        summary=result.summary,
        tags=result.tags,
        extracted_chars=result.extracted_chars,
    )


@router.post("/from-url", response_model=UploadOut, status_code=status.HTTP_201_CREATED)
async def upload_from_url(
    request: Request,
    body: FromUrlRequest,
    vault: VaultService = Depends(get_vault),
) -> UploadOut:
    llm = request.app.state.llm
    audit = getattr(request.app.state, "audit", None)

    try:
        result = await fetch_url_as_upload(
            url=body.url,
            vault=vault,
            llm=llm,
            audit=audit,
            conversation_id=body.conversation_id,
        )
    except AuthRequiredError as exc:
        # 422 is a more honest code here than 401 — the request itself
        # was fine, we just couldn't fetch the upstream resource.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    except FileTooLargeError as exc:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc)
        ) from exc

    return UploadOut(
        original_path=result.original_path,
        md_path=result.md_path,
        summary=result.summary,
        tags=result.tags,
        extracted_chars=result.extracted_chars,
    )


@router.get("/download")
def download(
    path: str,
    vault: VaultService = Depends(get_vault),
) -> StreamingResponse:
    """Stream a vault file as raw bytes. Used for uploaded originals (PDFs
    etc.) that don't fit the text-oriented /api/vault/file endpoint.
    """
    try:
        handle, size, name = open_vault_file_for_stream(vault, path)
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except (PathSafetyError, NotFoundError, VaultError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    mime, _ = mimetypes.guess_type(name)
    headers: dict[str, Any] = {
        "Content-Length": str(size),
        "Content-Disposition": f'attachment; filename="{name}"',
    }
    return StreamingResponse(
        handle,
        media_type=mime or "application/octet-stream",
        headers=headers,
    )
