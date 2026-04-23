from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_vault, require_auth
from app.vault import NotFoundError, PathSafetyError, VaultError, VaultService, safe_resolve

router = APIRouter(
    prefix="/api/vault",
    tags=["vault"],
    dependencies=[Depends(require_auth)],
)

# Filesystem mtime precision varies per OS — half a second keeps us honest
# without flagging save-and-immediately-save-again as conflict.
_MTIME_EPSILON_S = 0.5


class VaultEntryOut(BaseModel):
    path: str
    is_dir: bool
    size: int | None


class FileContent(BaseModel):
    path: str
    content: str
    modified_at: datetime


class WriteRequest(BaseModel):
    content: str
    # If the client sends this, the server rejects the write with 409 when
    # the on-disk mtime is newer — i.e. someone else (usually the agent)
    # wrote the same file while the user was editing.
    expected_modified_at: datetime | None = None


def _map_vault_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PathSafetyError):
        return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    if isinstance(exc, NotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, VaultError):
        return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    raise exc


def _mtime_utc(path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


@router.get("/tree", response_model=list[VaultEntryOut])
def tree(path: str = "", vault: VaultService = Depends(get_vault)) -> list[VaultEntryOut]:
    try:
        entries = vault.list(path)
    except (PathSafetyError, NotFoundError, VaultError) as exc:
        raise _map_vault_error(exc) from exc
    return [
        VaultEntryOut(path=e.path, is_dir=e.is_dir, size=e.size) for e in entries
    ]


@router.get("/file", response_model=FileContent)
def read_file(path: str, vault: VaultService = Depends(get_vault)) -> FileContent:
    try:
        content = vault.read(path)
        target = safe_resolve(vault.root, path)
    except (PathSafetyError, NotFoundError, VaultError) as exc:
        raise _map_vault_error(exc) from exc
    return FileContent(path=path, content=content, modified_at=_mtime_utc(target))


@router.delete("/file", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    path: str,
    vault: VaultService = Depends(get_vault),
) -> None:
    try:
        vault.delete(path, actor="user")
    except (PathSafetyError, NotFoundError, VaultError) as exc:
        raise _map_vault_error(exc) from exc


@router.put("/file", response_model=FileContent)
def write_file(
    path: str,
    body: WriteRequest,
    vault: VaultService = Depends(get_vault),
) -> FileContent:
    # Conflict check before writing, if the client supplied a baseline.
    try:
        target = safe_resolve(vault.root, path)
    except PathSafetyError as exc:
        raise _map_vault_error(exc) from exc

    if body.expected_modified_at is not None and target.exists():
        actual = _mtime_utc(target)
        # Normalise: expected_modified_at should be tz-aware; coerce defensively.
        expected = body.expected_modified_at
        if expected.tzinfo is None:
            expected = expected.replace(tzinfo=timezone.utc)
        if (actual - expected).total_seconds() > _MTIME_EPSILON_S:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"File was modified on disk at {actual.isoformat()} "
                    f"(you loaded it at {expected.isoformat()}). Reload to merge."
                ),
            )

    try:
        vault.write(path, body.content, actor="user")
    except (PathSafetyError, VaultError) as exc:
        raise _map_vault_error(exc) from exc
    return FileContent(
        path=path, content=body.content, modified_at=_mtime_utc(target)
    )
