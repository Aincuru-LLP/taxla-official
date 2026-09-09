from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from fastapi.security import OAuth2PasswordRequestForm  # noqa: F401 — OAuth2 form parser is referenced in OpenAPI; keep import
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_async_db
from app.core.security import (
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    get_current_user,
    is_refresh_token_revoked,
    revoke_refresh_token,
    verify_password,
)
from app.models.domain import User
from app.schemas.auth import (
    RefreshResponse,
    TokenResponse,
    UserLoginRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Attach the HttpOnly refresh-token cookie to ``response``.

    HttpOnly + SameSite=Lax + (Secure in non-dev) keeps the refresh token
    out of JS reach; the browser still attaches it on same-site requests,
    which is what the Axios interceptor relies on.
    """
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
        max_age=settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path="/",
        secure=settings.refresh_cookie_secure,
        samesite=settings.COOKIE_SAMESITE,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: UserLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_async_db),
):
    """Email + password → short-lived access token in JSON, long-lived
    refresh token in an HttpOnly cookie.
    """
    result = await db.execute(select(User).where(User.email == payload.username))
    user = result.scalars().first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="Account is disabled")

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)
    _set_refresh_cookie(response, refresh_token)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_db),
):
    """Read the refresh cookie, validate it, rotate, and return a new
    access token. The old refresh token is added to the Redis blacklist so
    it cannot be replayed.
    """
    refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
        )

    from jose import JWTError, jwt as jose_jwt

    try:
        payload = jose_jwt.decode(
            refresh_token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if payload.get("typ") != REFRESH_TOKEN_TYPE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong token type for refresh",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing subject",
        )

    if await is_refresh_token_revoked(refresh_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked",
        )

    # Confirm the user still exists and is active. A revoked refresh token
    # plus a deleted user should look the same to the client.
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled",
        )

    # Rotate: blacklist old, issue new. Done in either order would be safe;
    # we blacklist first to keep a stolen token from being race-redeemed
    # against the new cookie.
    await revoke_refresh_token(refresh_token)
    new_refresh = create_refresh_token(subject=user.id)
    new_access = create_access_token(subject=user.id)
    _set_refresh_cookie(response, new_refresh)

    return RefreshResponse(access_token=new_access, token_type="bearer")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response):
    """Revoke the refresh token (best-effort) and clear the cookie. Always
    returns 204 even if the cookie was already invalid — logout must not
    leak whether a session existed.
    """
    refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if refresh_token:
        await revoke_refresh_token(refresh_token)
    _clear_refresh_cookie(response)
    # Mutate the injected Response in place — returning a fresh Response
    # here would discard the cookie-clear header the helper just set.
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)
