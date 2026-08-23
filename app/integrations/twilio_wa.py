"""Twilio WhatsApp adapter with an in-memory outbox for offline demo."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.config import get_settings
from app.db.database import Repository, get_repo

logger = logging.getLogger(__name__)

# Process-local outbox so the Streamlit simulator can show dispatched messages.
OUTBOX: list[dict] = []


class WhatsAppGateway:
    def __init__(self, repo: Optional[Repository] = None) -> None:
        self.settings = get_settings()
        self.repo = repo or get_repo()

    def send_text(
        self,
        to_phone: str,
        body: str,
        *,
        patient_id: Optional[str] = None,
        language: str = "en",
        ticket_id: Optional[str] = None,
    ) -> dict:
        record = {
            "id": f"wa-{uuid4().hex[:10]}",
            "to": to_phone,
            "from": self.settings.twilio_whatsapp_from,
            "body": body,
            "patient_id": patient_id,
            "language": language,
            "ticket_id": ticket_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "channel": "whatsapp",
            "live": False,
        }
        if self.settings.twilio_enabled:
            try:
                sid = self._twilio_send(to_phone, body)
                record["id"] = sid
                record["live"] = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("Twilio send failed, keeping outbox copy: %s", exc)
        OUTBOX.insert(0, record)
        self.repo.insert_message(
            record["id"],
            patient_id=patient_id,
            phone_number=to_phone,
            direction="OUT",
            content=body,
            language=language,
            ticket_id=ticket_id,
        )
        return record

    def _twilio_send(self, to_phone: str, body: str) -> str:
        from twilio.rest import Client

        dest = to_phone if to_phone.startswith("whatsapp:") else f"whatsapp:{to_phone}"
        client = Client(self.settings.twilio_account_sid, self.settings.twilio_auth_token)
        message = client.messages.create(
            from_=self.settings.twilio_whatsapp_from,
            to=dest,
            body=body,
        )
        return message.sid

    def recent_outbox(self, limit: int = 20) -> list[dict]:
        return OUTBOX[:limit]


def parse_twilio_inbound(form: dict) -> dict:
    """Normalize a Twilio WhatsApp webhook form payload."""
    from_number = (form.get("From") or "").replace("whatsapp:", "")
    media_url = form.get("MediaUrl0")
    media_type = form.get("MediaContentType0") or ""
    return {
        "phone_number": from_number,
        "text": form.get("Body") or "",
        "image_url": media_url if media_type.startswith("image/") else None,
        "audio_url": media_url if media_type.startswith("audio/") else None,
        "message_sid": form.get("MessageSid") or "",
    }
