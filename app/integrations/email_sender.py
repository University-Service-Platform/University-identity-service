"""
Outgoing email for password reset links, through an email provider's HTTPS API.

HTTPS rather than SMTP because free Render instances block outbound SMTP ports.
Providers (EMAIL_PROVIDER):
    brevo  - https://api.brevo.com/v3/smtp/email; a verified single sender (e.g. a Gmail
             address) is enough to email anyone, so no domain is needed
    resend - https://api.resend.com/emails; needs a verified domain to email other people
    log    - writes the message to the log instead of sending it (development only)
EMAIL_FROM takes "Name <address>" or a bare address.
"""
import logging
from email.utils import formataddr, parseaddr
from typing import Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger("identity.integrations.email")

BREVO_URL = "https://api.brevo.com/v3/smtp/email"
RESEND_URL = "https://api.resend.com/emails"
DEFAULT_SENDER_NAME = "University Services Platform"


class EmailDeliveryError(Exception):
    """The provider refused the message or could not be reached."""


class EmailSender:
    def __init__(self, provider: str, api_key: Optional[str], sender: str,
                 transport: Optional[httpx.BaseTransport] = None, timeout: float = 10.0):
        self.provider = provider
        self.api_key = api_key
        name, address = parseaddr(sender or "")
        self.sender_name = name or DEFAULT_SENDER_NAME
        self.sender_address = address
        self._transport = transport
        self._timeout = timeout

    def send(self, to: str, subject: str, text: str, html: str) -> None:
        if self.provider == "log":
            logger.warning("EMAIL_PROVIDER=log, not sending. To: %s | Subject: %s\n%s", to, subject, text)
            return
        if self.provider == "brevo":
            url, headers, body = BREVO_URL, {"api-key": self.api_key}, {
                "sender": {"name": self.sender_name, "email": self.sender_address},
                "to": [{"email": to}],
                "subject": subject,
                "textContent": text,
                "htmlContent": html,
            }
        elif self.provider == "resend":
            url, headers, body = RESEND_URL, {"Authorization": f"Bearer {self.api_key}"}, {
                "from": formataddr((self.sender_name, self.sender_address)),
                "to": [to],
                "subject": subject,
                "text": text,
                "html": html,
            }
        else:
            raise EmailDeliveryError(f"Unknown email provider '{self.provider}'.")

        try:
            with httpx.Client(transport=self._transport, timeout=self._timeout) as client:
                response = client.post(url, headers={**headers, "Accept": "application/json"}, json=body)
        except httpx.HTTPError as exc:
            raise EmailDeliveryError(f"{self.provider} could not be reached: {type(exc).__name__}") from exc
        if response.status_code >= 300:
            # The provider's message explains a refusal (unverified sender, bad key); it never holds the link
            raise EmailDeliveryError(f"{self.provider} answered {response.status_code}: {response.text[:300]}")


def get_email_sender() -> Optional[EmailSender]:
    """The configured sender, or None when EMAIL_PROVIDER is not set (FastAPI dependency)."""
    settings = get_settings()
    if not settings.email_provider:
        return None
    return EmailSender(settings.email_provider, settings.email_api_key, settings.email_from or "")
