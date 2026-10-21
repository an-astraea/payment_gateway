"""Email through Zoho Mail SMTP (smtp.zoho.in, port 465, SSL).
If SMTP credentials are empty, emails are printed to the console instead."""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from ..config import get_settings

log = logging.getLogger(__name__)


def send_email(to: str, subject: str, html: str, text: str) -> bool:
    """Returns True if the email was handed to Zoho, False if it was only logged or failed."""
    s = get_settings()
    if not s.smtp_enabled:
        log.warning("SMTP not configured. Email to %s\nSubject: %s\n%s", to, subject, text)
        return False
    msg = EmailMessage()
    msg["From"] = formataddr((s.mail_from_name, s.mail_from))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    try:
        if s.smtp_port == 465:
            with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, context=ssl.create_default_context(), timeout=30) as smtp:
                smtp.login(s.smtp_username, s.smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(s.smtp_username, s.smtp_password)
                smtp.send_message(msg)
        log.info("Email sent to %s: %s", to, subject)
        return True
    except Exception:  # never break a booking because an email failed
        log.exception("Email to %s failed: %s", to, subject)
        return False