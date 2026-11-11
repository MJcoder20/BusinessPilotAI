
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import User
from app.schemas.auth import RegisterRequest

from pwdlib import PasswordHash

DUMMY_PASSWORD_HASH = PasswordHash.recommended().hash(
    "BusinessPilot-Dummy-Password-Not-For-Login"
)

def register_user(
    db: Session,
    user_data: RegisterRequest,
) -> User:
    """Create a new employee account."""

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

    if not verify_password(password, user.password_hash):
        return None

    if not user.is_active:
        return None

    return user