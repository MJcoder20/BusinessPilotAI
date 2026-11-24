import smtplib
from email.message import EmailMessage

from app.core.config import settings


def send_verification_email(recipient: str, verification_url: str) -> bool:
    """Send a verification email through the configured SMTP provider."""
    if not settings.smtp_host or not settings.smtp_from_email:
        return False

    message = EmailMessage()
    message["Subject"] = "Verify your BusinessPilot account"
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message.set_content(
        "Welcome to BusinessPilot!\n\n"
        "Verify your email address using the link below. "
        f"The link expires in {settings.verification_token_expire_minutes} minutes.\n\n"
        f"{verification_url}\n\n"
        "If you did not create this account, you can ignore this email."
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
    return True
