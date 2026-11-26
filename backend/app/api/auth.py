import httpx
from fastapi.responses import JSONResponse
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limiter import limiter
from app.core.security import (
    create_access_token,
    decode_supabase_access_token,
)
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    ResendVerificationRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
    PasswordResetRequest,
    PasswordResetConfirmRequest,
)
from app.services.auth import (
    authenticate_user,
    create_verification_token,
    register_user,
    verify_email_token,
)
from app.services.email import send_verification_email
from app.services.supabase_auth import sync_supabase_user
from app.services.refresh_tokens import (
    issue_refresh_token,
    rotate_refresh_token,
    revoke_refresh_token,
)
from app.services.password_reset import (
    request_password_reset,
    confirm_password_reset,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])

supabase_bearer_scheme = HTTPBearer(auto_error=False)

REFRESH_COOKIE_NAME = "businesspilot_refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="none" if settings.app_env == "production" else "lax",
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="none" if settings.app_env == "production" else "lax",
        path=REFRESH_COOKIE_PATH,
    )


def validate_cookie_request_origin(request: Request) -> None:
    origin = request.headers.get("origin")

    allowed_origins = (
        {settings.frontend_origin.rstrip("/")}
        if settings.app_env == "production"
        else {
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
        }
    )

    if origin not in allowed_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid request origin.",
        )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("3/hour")
def register(
    request: Request,
    response: Response,
    user_data: RegisterRequest,
    db: Session = Depends(get_db),
):
    try:
        user = register_user(db, user_data)

        verification_token = create_verification_token(db, user)

        send_verification_email(
            recipient_email=user.email,
            full_name=user.full_name,
            verification_token=verification_token,
        )

        return user

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

@router.post("/verify-email")
@limiter.limit("10/minute")
def verify_email(
    request: Request,
    response: Response,
    verification_data: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    user = verify_email_token(db, verification_data.token)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification link is invalid or expired. Please request a new one.",
        )

    return {
        "message": "Email verified successfully. You can now log in."
    }

@router.post("/resend-verification")
@limiter.limit("3/hour")
def resend_verification(
    request: Request,
    response: Response,
    verification_data: ResendVerificationRequest,
    db: Session = Depends(get_db),
):
    normalized_email = str(verification_data.email).strip().lower()

    user = (
        db.query(User)
        .filter(User.email == normalized_email)
        .first()
    )

    if user and user.is_active and not user.is_verified:
        verification_token = create_verification_token(db, user)

        send_verification_email(
            recipient_email=user.email,
            full_name=user.full_name,
            verification_token=verification_token,
        )

    return {
        "message": "If an unverified account exists for this email, a verification email has been sent."
    }


@router.post("/password-reset/request")
@limiter.limit("3/hour")
def password_reset_request(
    request: Request,
    response: Response,
    reset_data: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    try:
        request_password_reset(
            db,
            str(reset_data.email).strip().lower(),
        )
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password-reset email could not be sent. Please try again later.",
        ) from None

    return {
        "message": (
            "If an eligible account exists for this email, "
            "a password-reset link has been sent."
        )
    }


@router.post("/password-reset/confirm")
@limiter.limit("5/minute")
def password_reset_confirm(
    request: Request,
    response: Response,
    reset_data: PasswordResetConfirmRequest,
    db: Session = Depends(get_db),
):
    success = confirm_password_reset(
        db,
        raw_token=reset_data.token,
        new_password=reset_data.new_password,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password-reset link is invalid, expired, or already used.",
        )

    return {
        "message": "Your password has been reset successfully. You can now log in."
    }


@router.post(
    "/login",
    response_model=TokenResponse,
)
@limiter.limit("5/minute")
def login(
    request: Request,
    response: Response,
    credentials: LoginRequest,
    db: Session = Depends(get_db),
):
    user = authenticate_user(
        db,
        credentials.email,
        credentials.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address before logging in.",
        )

    access_token = create_access_token(
        user_id=user.id,
        role=user.role,
    )

    refresh_token = issue_refresh_token(db, user.id)
    db.commit()

    set_refresh_cookie(response, refresh_token)

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=user,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
)
@limiter.limit("10/minute")
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    validate_cookie_request_origin(request)

    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is missing or invalid.",
        )

    result = rotate_refresh_token(db, raw_token)

    if result is None:
        error_response = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "detail": "Refresh token is invalid, expired, or revoked."
            },
        )

        clear_refresh_cookie(error_response)

        return error_response

    new_refresh_token, user = result

    access_token = create_access_token(
        user_id=user.id,
        role=user.role,
    )

    set_refresh_cookie(response, new_refresh_token)

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=user,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    validate_cookie_request_origin(request)

    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)

    if raw_token:
        revoke_refresh_token(db, raw_token)

    clear_refresh_cookie(response)


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.post(
    "/supabase/sync",
    response_model=UserResponse,
)
def sync_supabase_account(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        supabase_bearer_scheme
    ),
    db: Session = Depends(get_db),
):
    """Synchronize a verified Supabase identity with a local user."""

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired Supabase credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    access_token = credentials.credentials
    claims = decode_supabase_access_token(access_token)

    if claims is None:
        raise unauthorized

    try:
        user = sync_supabase_user(db, access_token, claims)
        return user

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase authentication service is temporarily unavailable.",
        ) from None

    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase authentication is not configured.",
        ) from None