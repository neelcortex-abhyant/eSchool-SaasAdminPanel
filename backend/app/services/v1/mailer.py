"""Plain-text SMTP mail. Returns False instead of raising, and never logs message bodies."""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger("eschool.mail")


def send_mail(to: str, subject: str, body: str) -> bool:
    """Send one message. False when mail is not configured or delivery fails."""
    settings = get_settings()
    domain = to.rsplit("@", 1)[-1]
    if not settings.mail_configured:
        logger.warning("mail_not_configured to_domain=%s", domain)
        return False

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    context = ssl.create_default_context()
    try:
        if settings.smtp_use_ssl:
            client = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10, context=context)
        else:
            client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
        with client:
            if settings.smtp_use_tls and not settings.smtp_use_ssl:
                client.starttls(context=context)
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            client.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        # The body holds a single-use link, so only the error type is logged.
        logger.warning("mail_send_failed to_domain=%s error=%s", domain, type(exc).__name__)
        return False
    logger.info("mail_sent to_domain=%s", domain)
    return True
