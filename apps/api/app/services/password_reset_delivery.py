from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import quote_plus

from ..settings import settings

logger = logging.getLogger("omniflow.api.auth")


def send_password_reset_email(to_email: str, token: str) -> None:
    if not settings.smtp_host or not settings.smtp_from_email:
        raise RuntimeError("smtp delivery is not configured")

    reset_url = f"{settings.password_reset_url_base}?token={quote_plus(token)}"
    message = EmailMessage()
    message["Subject"] = "OmniFlow password reset"
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message.set_content(
        "You requested a password reset for your OmniFlow account.\n\n"
        f"Use this link to reset your password: {reset_url}\n\n"
        "If you did not request this, you can ignore this message."
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)

    logger.info("password_reset_email_sent")
