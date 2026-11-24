import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import EmailVerificationToken, User


def create_email_verification_token(db: Session, user: User) -> str:
    """Create a high-entropy token; only its SHA-256 digest is persisted."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)

    # Invalidate outstanding links when a new one is issued.
    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id,
        EmailVerificationToken.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)

    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=now + timedelta(
                minutes=settings.verification_token_expire_minutes
            ),
        )
    )
    db.commit()
    return raw_token


def verify_email_token(db: Session, raw_token: str) -> User | None:
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    token_record = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.token_hash == token_hash)
        .with_for_update()
        .first()
    )
    now = datetime.now(timezone.utc)

    if token_record is None or token_record.used_at is not None:
        return None

    expires_at = token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        return None

    user = db.query(User).filter(User.id == token_record.user_id).first()
    if user is None or not user.is_active:
        return None

    token_record.used_at = now
    user.is_email_verified = True
    db.commit()
    db.refresh(user)
    return user
