from datetime import datetime, timedelta, timezone
from typing import Any, Union
import hashlib
import bcrypt
from jose import jwt
import redis.asyncio as aioredis
from app.core.config import settings


def _truncate_password(plain_password: str) -> bytes:
    """Bcrypt only looks at the first 72 bytes. Truncate so passwords like
    a passphrase still hash instead of raising.
    """
    return plain_password.encode("utf-8")[:72]


def _utc_now() -> datetime:
    """Timezone-aware UTC now. Python 3.12+ deprecates datetime.utcnow()."""
    return datetime.now(timezone.utc)


# Access token: short-lived (~15 min), returned to the client in JSON and
# held in memory. Refresh token: long-lived (~7 days), stored as an HttpOnly
# cookie. Both are HS256 JWTs signed with the same secret but distinguished
# by their `typ` claim.
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def create_access_token(
    subject: Union[str, Any], expires_delta: timedelta = None
) -> str:
    if expires_delta:
        expire = _utc_now() + expires_delta
    else:
        expire = _utc_now() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject), "typ": ACCESS_TOKEN_TYPE}
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, Any], expires_delta: timedelta = None
) -> str:
    """Mint a refresh JWT. Same secret as access tokens; distinguished by
    ``typ=refresh`` so we can refuse to use one where the other is expected.
    """
    if expires_delta:
        expire = _utc_now() + expires_delta
    else:
        expire = _utc_now() + timedelta(
            minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject), "typ": REFRESH_TOKEN_TYPE}
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def _token_fingerprint(token: str) -> str:
    """Stable, short key for the Redis blacklist. Hashing keeps us from
    storing the raw token, so a Redis dump alone cannot replay sessions.
    """
    return hashlib.sha256(token.encode()).hexdigest()


async def revoke_refresh_token(token: str) -> None:
    """Add a refresh token to the Redis blacklist with TTL = its remaining
    lifetime. After it expires naturally the blacklist entry falls out and
    storage stays bounded.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False},
        )
    except Exception:
        return
    exp = payload.get("exp")
    if not exp:
        return
    now_ts = int(_utc_now().timestamp())
    ttl = max(int(exp) - now_ts, 1)
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        await r.set(f"revoked_refresh:{_token_fingerprint(token)}", "1", ex=ttl)
    finally:
        await r.aclose()


async def is_refresh_token_revoked(token: str) -> bool:
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        return bool(await r.exists(f"revoked_refresh:{_token_fingerprint(token)}"))
    finally:
        await r.aclose()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Bcrypt hash check. The dummy 60-char hash the tests use ("x" * 60)
    # never matches a real password — tests mint JWTs directly, so login
    # is not exercised there.
    try:
        return bcrypt.checkpw(
            _truncate_password(plain_password),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        # Malformed hash (e.g. dummy "x" * 60 from a fixture). Treat as
        # non-match so the login endpoint returns a clean 401.
        return False

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(
        _truncate_password(password), bcrypt.gensalt()
    ).decode("utf-8")

from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_async_db
from app.models.domain import User
from jose import JWTError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_async_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        if payload.get("typ", ACCESS_TOKEN_TYPE) != ACCESS_TOKEN_TYPE:
            # Refresh tokens must never be accepted as Bearer creds.
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user

def require_roles(*allowed_roles: str):
    """FastAPI dependency factory that 403s if the caller's role is not in
    ``allowed_roles``.

    Used as::

        @router.get("/foo", dependencies=[Depends(require_roles("OPERATOR", "BRANCH_ADMIN"))])
        async def foo(...): ...

    or, when the handler also needs the user::

        async def foo(current_user: User = Depends(require_roles("OPERATOR"))): ...
    """
    async def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Operation not permitted: role '{current_user.role}' "
                    f"not in {list(allowed_roles)}"
                ),
            )
        return current_user
    return role_checker


async def assert_branch_scope(user: User, application) -> None:
    """Raise 403 unless ``user`` may act on ``application``.

    Rules:
      * SUPER_ADMIN  -> always allowed.
      * All other roles -> ``user.branch_id`` must equal ``application.branch_id``.
        Users with no branch_id (NULL) get 403 — branchless users are
        a misconfiguration, not an override.

    Pass a freshly-loaded ``Application`` (not the relationship) — the helper
    only reads ``application.branch_id`` so any object with that attribute
    is acceptable.
    """
    if user.role == "SUPER_ADMIN":
        return
    if user.branch_id is None or application.branch_id is None:
        raise HTTPException(
            status_code=403,
            detail=(
                "Cross-branch access denied: caller has no branch assignment"
            ),
        )
    if user.branch_id != application.branch_id:
        raise HTTPException(
            status_code=403,
            detail="Cross-branch access denied: caller's branch does not own this application",
        )
