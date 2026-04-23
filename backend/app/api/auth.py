import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.api.deps import get_settings
from app.config import Settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


class AuthStatus(BaseModel):
    authed: bool


@router.post("/login", response_model=AuthStatus)
def login(
    body: LoginRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> AuthStatus:
    expected = settings.auth_password or ""
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AUTH_PASSWORD is not configured on the server",
        )
    if not secrets.compare_digest(body.password, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid password",
        )
    request.session["authed"] = True
    return AuthStatus(authed=True)


@router.post("/logout", response_model=AuthStatus)
def logout(request: Request) -> AuthStatus:
    request.session.clear()
    return AuthStatus(authed=False)


@router.get("/me", response_model=AuthStatus)
def me(request: Request) -> AuthStatus:
    return AuthStatus(authed=bool(request.session.get("authed")))
