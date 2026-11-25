
from uuid import UUID

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import User
from app.services.auth import DUMMY_PASSWORD_HASH


def sync_supabase_user(
    db: Session,
    access_token: str,
    claims: dict,
) -> User:
    """Verify a Supabase user and synchronize it with the local database."""

    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise RuntimeError("Supabase authentication is not configured.")

    supabase_user_id = str(UUID(claims["sub"]))

    # Verify the identity and email confirmation directly with Supabase.
    response = httpx.get(
        f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
        headers={
            "apikey": settings.supabase_publishable_key,
            "Authorization": f"Bearer {access_token}",
        },
        timeout=10.0,
    )

    if response.status_code != 200:
        raise ValueError("Unable to verify the Supabase account.")

    supabase_user = response.json()

    if str(supabase_user.get("id", "")) != supabase_user_id:
        raise ValueError("Supabase identity does not match the access token.")

    if not supabase_user.get("email_confirmed_at"):
        raise ValueError("Please confirm your email address first.")

    email = supabase_user.get("email")

    if not isinstance(email, str) or not email.strip():
        raise ValueError("The Supabase account has no valid email address.")

    email = email.strip().lower()

    token_email = claims.get("email")
    if not isinstance(token_email, str) or token_email.strip().lower() != email:
        raise ValueError("Supabase email does not match the access token.")

    # Return an already-linked account without changing its existing role.
    user = (
        db.query(User)
        .filter(User.supabase_user_id == supabase_user_id)
        .first()
    )

    if user is not None:
        if not user.is_active or user.email.lower() != email:
            raise ValueError("This account cannot be used.")

        return user

    # Never automatically attach a new Supabase identity to a legacy account.
    existing_email_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_email_user is not None:
        raise ValueError(
            "An account with this email already exists. "
            "Please contact support to link your accounts safely."
        )

    metadata = supabase_user.get("user_metadata") or {}
    full_name = metadata.get("full_name")

    if not isinstance(full_name, str) or len(full_name.strip()) < 2:
        full_name = email.split("@", 1)[0]

    full_name = full_name.strip()[:150]

    user = User(
        supabase_user_id=supabase_user_id,
        full_name=full_name,
        email=email,
        password_hash=DUMMY_PASSWORD_HASH,
        role="employee",
        is_active=True,
        is_verified=True,
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()

        # Another request may have created the same identity concurrently.
        user = (
            db.query(User)
            .filter(User.supabase_user_id == supabase_user_id)
            .first()
        )

        if user is not None and user.is_active and user.email.lower() == email:
            return user

        raise ValueError(
            "An account with this email already exists or could not be created."
        ) from None

    return user
