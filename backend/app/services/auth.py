
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models import User
from app.schemas.auth import RegisterRequest


DUMMY_PASSWORD_HASH = PasswordHash.recommended().hash(
    "BusinessPilot-Dummy-Password-Not-For-Login"
)


def register_user(
    db: Session,
    user_data: RegisterRequest,
) -> User:
    """Create a new unverified employee account."""
    normalized_email = str(user_data.email).strip().lower()

    existing_user = (
        db.query(User)
        .filter(User.email == normalized_email)
        .first()
    )

    if existing_user:
        raise ValueError("An account with this email already exists.")

    user = User(
        full_name=user_data.full_name.strip(),
        email=normalized_email,
        password_hash=hash_password(user_data.password),
        role="employee",
        is_active=True,
        is_verified=False,
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise ValueError(
            "An account with this email already exists."
        ) from None

    return user


def create_verification_token(
    db: Session,
    user: User,
) -> str:
    """Generate and store a hashed, expiring email verification token."""
    raw_token = secrets.token_urlsafe(32)

    user.verification_token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    user.verification_token_expires_at = (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=settings.email_verification_expire_minutes
        )
    )

    db.commit()

    return raw_token

def verify_email_token(
    db: Session,
    raw_token: str,
) -> User | None:
    """Verify an email address using a valid, unexpired token."""
    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    user = (
        db.query(User)
        .filter(User.verification_token_hash == token_hash)
        .first()
    )

    if user is None:
        return None

    expires_at = user.verification_token_expires_at

    if (
        expires_at is None
        or expires_at <= datetime.now(timezone.utc)
    ):
        user.verification_token_hash = None
        user.verification_token_expires_at = None
        db.commit()
        return None

    user.is_verified = True
    user.verification_token_hash = None
    user.verification_token_expires_at = None

    db.commit()
    db.refresh(user)

    return user


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> User | None:
    """Authenticate an active user with email and password."""
    normalized_email = email.strip().lower()

    user = (
        db.query(User)
        .filter(User.email == normalized_email)
        .first()
    )

    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        return None

    # Supabase-linked accounts must authenticate through Supabase.
    if user.supabase_user_id is not None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        return None

    if not verify_password(password, user.password_hash):
        return None

    if not user.is_active:
        return None

    return user
