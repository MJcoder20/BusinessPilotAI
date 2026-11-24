
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_verification_email(
    recipient_email: str,
    full_name: str,
    verification_token: str,
) -> None:
    """Send an account verification email through SMTP."""
    if not all(
        [
            settings.smtp_host,
            settings.smtp_from_email,
        ]
    ):
        if settings.app_env == "development":
            logger.warning(
                "SMTP is not configured. Verification email cannot be sent to %s.",
                recipient_email,
            )
            return

        raise RuntimeError("Email delivery is not configured.")

    verification_url = (
        f"{settings.frontend_origin.rstrip('/')}"
        f"/?verify_email={verification_token}"
    )

    message = EmailMessage()
    message["Subject"] = "Verify your BusinessPilot AI account"
    message["From"] = settings.smtp_from_email
    message["To"] = recipient_email

    message.set_content(
        f"""Hello {full_name},

Thank you for registering with BusinessPilot AI.

Please verify your email address by opening this link:

{verification_url}

This link expires in {settings.email_verification_expire_minutes} minutes.

If you did not create this account, you can ignore this email.

BusinessPilot AI Team
"""
    )

    try:
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=15,
        ) as server:
            if settings.smtp_use_tls:
                server.starttls()

            if settings.smtp_username and settings.smtp_password:
                server.login(
                    settings.smtp_username,
                    settings.smtp_password,
                )

            server.send_message(message)

    except (OSError, smtplib.SMTPException):
        logger.exception("Failed to send verification email.")
        raise RuntimeError("Unable to send verification email.") from None
