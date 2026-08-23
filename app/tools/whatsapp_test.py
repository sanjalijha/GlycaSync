"""Check the WhatsApp delivery path and optionally send a test message.

    python -m app.tools.whatsapp_test                    # report configuration only
    python -m app.tools.whatsapp_test +919821487690      # also send a test message
"""

from __future__ import annotations

import argparse
import sys

from app.config import get_settings
from app.db.database import get_repo
from app.integrations.twilio_wa import WhatsAppGateway

DEFAULT_BODY = (
    "GlycaSync test message. Your care team has connected this number for glucose "
    "check-ins. Reply with your reading any time. No action needed right now."
)


def describe_config() -> tuple[bool, list[str]]:
    settings = get_settings()
    missing = []
    if not settings.twilio_account_sid:
        missing.append("TWILIO_ACCOUNT_SID")
    if not settings.twilio_auth_token:
        missing.append("TWILIO_AUTH_TOKEN")
    if not settings.twilio_whatsapp_from:
        missing.append("TWILIO_WHATSAPP_FROM")

    local_webhook = settings.webhook_url.startswith("http://localhost")

    print("WhatsApp connection")
    print(f"  Twilio credentials : {'present' if not missing else 'missing ' + ', '.join(missing)}")
    print(f"  Sender             : {settings.twilio_whatsapp_from or '—'}")
    print(f"  Inbound webhook    : {settings.webhook_url}")
    print(f"  Signature check    : {'on' if settings.twilio_validate_signature else 'OFF'}")
    print(f"  Outbound enabled   : {settings.twilio_enabled}")

    if local_webhook:
        print()
        print("  The webhook URL is local, so Twilio cannot reach it. Expose it with")
        print("  `ngrok http 8000` and set PUBLIC_BASE_URL to the HTTPS address ngrok")
        print("  prints, then paste that same URL into the Twilio sandbox settings.")
        print("  The signature is verified against this URL, so the two must match.")

    return settings.twilio_enabled, missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify WhatsApp delivery.")
    parser.add_argument("to", nargs="?", help="Destination number in E.164 form, e.g. +919821487690")
    parser.add_argument("--body", default=DEFAULT_BODY)
    args = parser.parse_args()

    enabled, missing = describe_config()

    if not args.to:
        return 0

    if not enabled:
        print()
        print(f"Cannot deliver to {args.to}: Twilio is not configured.")
        print("To enable delivery:")
        print("  1. Create a Twilio account and open Messaging > Try it out > WhatsApp sandbox.")
        print(f"  2. From {args.to}, send the sandbox join code to Twilio's sandbox number.")
        print("     WhatsApp only allows business-initiated messages to numbers that have opted in.")
        print(f"  3. Put {', '.join(missing) or 'the credentials'} in .env.")
        print("  4. Re-run this command.")
        print()
        print("Recording the message in the outbound log instead so the flow can still be traced.")

    record = WhatsAppGateway(get_repo()).send_text(args.to, args.body)
    print()
    print(f"  Delivered : {record['live']}")
    print(f"  Reference : {record['id']}")
    print(f"  To        : {record['to']}")
    print(f"  Body      : {record['body']}")
    return 0 if record["live"] or not enabled else 1


if __name__ == "__main__":
    sys.exit(main())
