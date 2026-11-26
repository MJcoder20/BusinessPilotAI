
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models import PasswordResetToken, User
from app.services.email import send_password_reset_email
from app.services.refresh_tokens import revoke_all_user_refresh_tokens


def hash_reset_token(token: str) -> str:
    """Return the SHA-256 hash of a password-reset token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def request_password_reset(db: Session, email: str) -> None:
    """Create a reset token and send an email when the account is eligible."""
    normalized_email = email.strip().lower()

    user = (
        db.query(User)
        .filter(User.email == normalized_email)
        .first()
    )

    # Do not reveal whether an account exists or is managed by Supabase.
    if (
        user is None
        or not user.is_active
        or not user.is_verified
        or user.supabase_user_id is not None
    ):
        return

    now = datetime.now(timezone.utc)

    # Invalidate previous unused reset tokens for this user.
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update(
        {PasswordResetToken.used_at: now},
        synchronize_session=False,
    )

    raw_token = secrets.token_urlsafe(48)

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_reset_token(raw_token),
        expires_at=now + timedelta(
            minutes=settings.password_reset_expire_minutes
        ),
    )

    db.add(reset_token)
    db.commit()

    try:
        send_password_reset_email(
            recipient_email=user.email,
            full_name=user.full_name,
            reset_token=raw_token,
        )
    except RuntimeError:
        # Do not leave an active token if email delivery fails.
        reset_token.used_at = datetime.now(timezone.utc)
        db.commit()
        raise


def confirm_password_reset(
    db: Session,
    raw_token: str,
    new_password: str,
) -> bool:
    """Validate a reset token, update the password, and revoke sessions."""
    token_hash = hash_reset_token(raw_token)

    reset_token = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash)
        .with_for_update()
        .first()
    )

    if reset_token is None or reset_token.used_at is not None:
        return False

    now = datetime.now(timezone.utc)

    expires_at = reset_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= now:
        return False

    user = (
        db.query(User)
        .filter(User.id == reset_token.user_id)
        .with_for_update()
        .first()
    )

    if (
        user is None
        or not user.is_active
        or not user.is_verified
        or user.supabase_user_id is not None
    ):
        return False

    user.password_hash = hash_password(new_password)
    reset_token.used_at = now

    # Invalidate all other outstanding reset tokens.
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.id != reset_token.id,
        PasswordResetToken.used_at.is_(None),
    ).update(
        {PasswordResetToken.used_at: now},
        synchronize_session=False,
    )

    # Invalidate all existing refresh sessions.
    revoke_all_user_refresh_tokens(db, user.id)

    db.commit()

    return True
