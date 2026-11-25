from collections.abc import Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    decode_access_token,
    decode_supabase_access_token,
)
from app.models import User


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Retrieve the active user associated with a valid access token."""

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    token = credentials.credentials

    # First, preserve the existing legacy JWT authentication.
    payload = decode_access_token(token)

    if payload is not None:
        user = (
            db.query(User)
            .filter(User.id == int(payload["sub"]))
            .first()
        )
    else:
        # Otherwise, verify the token as a Supabase ES256 JWT.
        payload = decode_supabase_access_token(token)

        if payload is None:
            raise unauthorized

        user = (
            db.query(User)
            .filter(User.supabase_user_id == payload["sub"])
            .first()
        )

    if user is None or not user.is_active:
        raise unauthorized

    return user

def require_roles(*allowed_roles: str) -> Callable:
    """
    Restrict an endpoint to users with specific roles.
    """

    def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return current_user

    return role_checker