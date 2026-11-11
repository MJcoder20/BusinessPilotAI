
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import RefreshToken, User


def hash_refresh_token(token: str) -> str:
    """Return the SHA-256 hash of a refresh token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_refresh_token(db: Session, user_id: int) -> str:
    """Generate a secure opaque token and store only its hash."""
    raw_token = secrets.token_urlsafe(48)

    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )

    token_record = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(raw_token),
        expires_at=expires_at,
    )

    db.add(token_record)
    db.flush()

    return raw_token


def rotate_refresh_token(
    db: Session,
    raw_token: str,
) -> tuple[str, User] | None:
    """Revoke an existing token and issue a replacement."""
    token_hash = hash_refresh_token(raw_token)

    stored_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .with_for_update()
        .first()
    )

    if stored_token is None:
        return None

    now = datetime.now(timezone.utc)

    expires_at = stored_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if stored_token.revoked_at is not None or expires_at <= now:
        return None

    user = (
        db.query(User)
        .filter(User.id == stored_token.user_id)
        .first()
    )

    if user is None or not user.is_active:
        return None

    stored_token.revoked_at = now

    new_token = issue_refresh_token(db, user.id)

    db.commit()

    return new_token, user


def revoke_refresh_token(db: Session, raw_token: str) -> bool:
    """Revoke a refresh token if it exists and is still active."""
    token_hash = hash_refresh_token(raw_token)

    stored_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .with_for_update()
        .first()
    )

    if stored_token is None or stored_token.revoked_at is not None:
        return False

    stored_token.revoked_at = datetime.now(timezone.utc)
    db.commit()

    return True
