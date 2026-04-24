"""GET /api/models — list the configured models + the default."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.api.deps import require_auth

router = APIRouter(
    prefix="/api/models",
    tags=["models"],
    dependencies=[Depends(require_auth)],
)


class ModelOut(BaseModel):
    name: str  # display name / key (the value stored on conversations)
    id: str  # actual model id passed to the provider (e.g. gpt-4o-mini)


class ModelsListOut(BaseModel):
    models: list[ModelOut]
    default: str


@router.get("", response_model=ModelsListOut)
def list_models(request: Request) -> ModelsListOut:
    llms = getattr(request.app.state, "llms", {}) or {}
    default = getattr(request.app.state, "default_model", None) or ""
    return ModelsListOut(
        models=[ModelOut(name=name, id=provider.model) for name, provider in llms.items()],
        default=default,
    )
