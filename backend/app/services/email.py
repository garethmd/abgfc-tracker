"""Sending email. One method, three backends.

Production goes over the provider's **HTTPS API**, never SMTP: DigitalOcean blocks
outbound SMTP ports on droplets, so a relay would hang rather than fail cleanly.
`httpx` is already a dependency, so there is nothing new to install.

Development and tests use the console backend, which logs the message (link included)
and sends nothing - no network in tests, and you can click the invite link out of the
API log.

`email_reply_to` matters: the sending domain has no MX record, so a parent replying to
a noreply@ address gets a bounce. Point it at a mailbox somebody reads.
"""

import logging

import httpx

from app.config import Settings

log = logging.getLogger("abgfc.email")
RESEND_ENDPOINT = "https://api.resend.com/emails"
MAILGUN_ENDPOINT = "https://api.mailgun.net/v3/{domain}/messages"


class EmailError(Exception):
    """Sending failed. Callers decide whether that is fatal - for an invite it isn't:
    the coach still has the link and can send it by hand."""


class EmailService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, to: str, subject: str, body: str) -> None:
        s = self.settings
        if s.email_backend == "console":
            log.info("EMAIL to=%s subject=%s\n%s", to, subject, body)
            return
        try:
            self._post(to, subject, body)
        except httpx.HTTPError as e:
            # Never log the body: it carries a single-use sign-in link.
            log.warning("Email to %s failed: %s", to, e.__class__.__name__)
            raise EmailError(str(e)) from e

    def _post(self, to: str, subject: str, body: str) -> None:
        s = self.settings
        if s.email_backend == "resend":
            payload = {"from": s.email_from, "to": [to], "subject": subject, "text": body}
            if s.email_reply_to:
                payload["reply_to"] = [s.email_reply_to]
            r = httpx.post(
                RESEND_ENDPOINT,
                headers={"Authorization": f"Bearer {s.email_api_key}"},
                json=payload,
                timeout=10,
            )
        else:  # mailgun
            data = {"from": s.email_from, "to": to, "subject": subject, "text": body}
            if s.email_reply_to:
                data["h:Reply-To"] = s.email_reply_to
            r = httpx.post(
                MAILGUN_ENDPOINT.format(domain=s.mailgun_domain),
                auth=("api", s.email_api_key),
                data=data,
                timeout=10,
            )
        r.raise_for_status()
