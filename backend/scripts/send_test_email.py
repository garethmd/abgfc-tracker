"""Send one email with the configured backend, to prove the setup before a parent does.

    uv run python -m scripts.send_test_email you@example.com

On the droplet:

    docker compose -f docker-compose.prod.yml exec api \
        uv run python -m scripts.send_test_email you@example.com

Prints what it is about to do, so a misconfiguration (still on the console backend, no
key, wrong From) is obvious before anything is sent.
"""

import sys
from datetime import datetime

from app.config import get_settings
from app.services.email import EmailError, EmailService


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    to = sys.argv[1]
    s = get_settings()
    print(f"backend   {s.email_backend}")
    print(f"from      {s.email_from}")
    print(f"reply-to  {s.email_reply_to or '(none - replies will bounce)'}")
    print(f"api key   {'set' if s.email_api_key else 'MISSING'}")
    if s.email_backend == "mailgun":
        print(f"domain    {s.mailgun_domain}")
    print(f"links     {s.public_base_url}")
    print(f"sending   {to}")
    if s.email_backend == "console":
        print("\n! console backend: this only logs, it does not send.")
    try:
        EmailService(s).send(
            to,
            "ABGFC test email",
            "This is a test from the ABGFC app.\n\n"
            f"Sent at {datetime.now():%Y-%m-%d %H:%M}.\n\n"
            "If you can see this, invitations and sign-in links will reach parents.\n"
            "Try replying to it as well - the reply should land in a real mailbox.\n",
        )
    except EmailError as e:
        print(f"\nFAILED: {e}")
        return 1
    if s.email_backend == "console":
        print("\nLogged only - nothing was sent. Set ABGFC_EMAIL_BACKEND to send for real.")
    else:
        print("\nAccepted by the provider. Check the inbox - and the spam folder, which")
        print("is the usual culprit when DKIM or DMARC isn't right yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
