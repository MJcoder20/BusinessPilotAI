from uuid import UUID
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from datetime import datetime, timedelta, timezone

from functools import lru_cache
import jwt

from app.core.config import settings


def create_access_token(
    user_id: int,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token."""

    now = datetime.now(timezone.utc)
    expires_at = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )

    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": expires_at,
        "type": "access",
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict | None:
    """Validate a JWT access token and return its claims."""

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        if payload.get("type") != "access":
            return None

        subject = payload.get("sub")

        if not isinstance(subject, str) or not subject.isdigit():
            return None

        if int(subject) <= 0:
            return None

        if payload.get("role") not in {"admin", "manager", "employee"}:
            return None

        return payload

    except jwt.InvalidTokenError:
        return None



@lru_cache(maxsize=1)
def get_supabase_jwks_client():
    """Create a cached client for Supabase public signing keys."""
    if not settings.supabase_url:
        return None

    jwks_url = (
        f"{settings.supabase_url.rstrip('/')}"
        "/auth/v1/.well-known/jwks.json"
    )

    return jwt.PyJWKClient(jwks_url)


def decode_supabase_access_token(token: str) -> dict | None:
    """Verify a Supabase ES256 access token and return its claims."""
    try:
        if not settings.supabase_url:
            return None

        jwks_client = get_supabase_jwks_client()

        if jwks_client is None:
            return None

        signing_key = jwks_client.get_signing_key_from_jwt(token)

        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
            issuer=f"{settings.supabase_url.rstrip('/')}/auth/v1",
            options={
                "require": ["exp", "iat", "sub", "iss", "aud"],
            },
        )

        subject = payload.get("sub")

        if not isinstance(subject, str):
            return None

        try:
            UUID(subject)
        except ValueError:
            return None

        if payload.get("role") != "authenticated":
            return None

        if payload.get("is_anonymous") is not False:
            return None

        return payload

    except (jwt.PyJWTError, OSError, ValueError):
        return None


# Argon2 is selected by pwdlib's recommended configuration
# because argon2-cffi is installed.
password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a password using the recommended password hashing algorithm."""
    return password_hasher.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """Verify a password against its stored hash."""

    try:
        return password_hasher.verify(
            plain_password,
            hashed_password,
        )
    except (UnknownHashError, ValueError):
        return False
