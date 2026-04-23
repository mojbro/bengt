from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_vault, require_auth
from app.vault import NotFoundError, PathSafetyError, VaultError, VaultService

router = APIRouter(
    prefix="/api/vault",
    tags=["vault"],
    dependencies=[Depends(require_auth)],
)


class VaultEntryOut(BaseModel):
    path: str
    is_dir: bool
    size: int | None


class FileContent(BaseModel):
    path: str
    content: str


class WriteRequest(BaseModel):
    content: str


def _map_vault_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PathSafetyError):
        return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    if isinstance(exc, NotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, VaultError):
        return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    raise exc


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
    except (PathSafetyError, NotFoundError, VaultError) as exc:
        raise _map_vault_error(exc) from exc
    return FileContent(path=path, content=content)


@router.put("/file", response_model=FileContent)
def write_file(
    path: str,
    body: WriteRequest,
    vault: VaultService = Depends(get_vault),
) -> FileContent:
    try:
        vault.write(path, body.content, actor="user")
    except (PathSafetyError, VaultError) as exc:
        raise _map_vault_error(exc) from exc
    return FileContent(path=path, content=body.content)
