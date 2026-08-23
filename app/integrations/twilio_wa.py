"""Twilio WhatsApp adapter with an in-memory outbox for offline demo."""

from __future__ import annotations

import logging
import mimetypes
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import httpx

from app.config import get_settings
from app.db.database import Repository, get_repo

logger = logging.getLogger(__name__)

SANDBOX_FROM = "whatsapp:+14155238886"


def normalize_e164(phone: str) -> str:
    """Turn a typed Indian or E.164 number into +<digits>."""
    raw = (phone or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return ""
    if raw.startswith("+"):
        return "+" + digits
    if len(digits) == 10:
        return "+91" + digits
    if len(digits) == 12 and digits.startswith("91"):
        return "+" + digits
    return "+" + digits


def normalize_whatsapp_from(value: str) -> str:
    number = normalize_e164(value.replace("whatsapp:", "") if value else "")
    return f"whatsapp:{number}" if number else SANDBOX_FROM


def verify_twilio(account_sid: str, auth_token: str) -> tuple[bool, str]:
    """Ask Twilio whether these credentials are real, without sending a message."""
    sid = (account_sid or "").strip()
    token = (auth_token or "").strip()
    if not sid or not token:
        return False, "Account SID and auth token are both required."
    try:
        from twilio.rest import Client

        account = Client(sid, token).api.accounts(sid).fetch()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    return True, account.friendly_name or "Twilio account"


def connect_whatsapp(
    *,
    account_sid: str,
    auth_token: str,
    whatsapp_from: str = SANDBOX_FROM,
    public_base_url: str = "",
    content_sid: str = "",
    verify: bool = True,
) -> tuple[bool, str]:
    """Check credentials, persist them, and reload settings for this process."""
    from app.config import apply_settings_updates, get_settings

    sid = account_sid.strip()
    token = auth_token.strip()
    sender = normalize_whatsapp_from(whatsapp_from)
    if verify:
        ok, detail = verify_twilio(sid, token)
        if not ok:
            return False, detail

    updates = {
        "TWILIO_ACCOUNT_SID": sid,
        "TWILIO_AUTH_TOKEN": token,
        "TWILIO_WHATSAPP_FROM": sender,
        "TWILIO_VALIDATE_SIGNATURE": "true",
        "TWILIO_CONTENT_SID": content_sid.strip(),
    }
    base = (public_base_url or "").strip()
    if base:
        updates["PUBLIC_BASE_URL"] = base.rstrip("/")
    apply_settings_updates(updates)
    settings = get_settings()
    return True, settings.webhook_url


def disconnect_whatsapp() -> None:
    from app.config import apply_settings_updates

    apply_settings_updates(
        {
            "TWILIO_ACCOUNT_SID": "",
            "TWILIO_AUTH_TOKEN": "",
        }
    )


# WhatsApp sends voice notes as audio/ogg, which mimetypes does not always know.
_EXTENSIONS = {
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/amr": ".amr",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

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
            "error": "",
        }
        if self.settings.twilio_enabled:
            try:
                sid = self._twilio_send(to_phone, body)
                record["id"] = sid
                record["live"] = True
            except Exception as exc:  # noqa: BLE001
                record["error"] = str(exc)
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
        sender = self.settings.twilio_whatsapp_from
        try:
            message = client.messages.create(from_=sender, to=dest, body=body)
            return message.sid
        except Exception:
            if not self.settings.twilio_content_sid:
                raise
            # Outside a 24-hour session WhatsApp only accepts an approved template.
            message = client.messages.create(
                from_=sender,
                to=dest,
                content_sid=self.settings.twilio_content_sid,
            )
            return message.sid

    def recent_outbox(self, limit: int = 20) -> list[dict]:
        return OUTBOX[:limit]


def inbound_content(inbound: dict) -> str:
    """Human-readable body for a logged inbound WhatsApp message."""
    parts: list[str] = []
    text = (inbound.get("text") or "").strip()
    if text:
        parts.append(text)
    kinds: list[str] = []
    for media in inbound.get("media") or []:
        kind = (media.get("content_type") or "").lower()
        if kind.startswith("image/"):
            kinds.append("photo")
        elif kind.startswith("audio/"):
            kinds.append("voice note")
        elif media.get("url"):
            kinds.append("attachment")
    if inbound.get("image_url") and "photo" not in kinds:
        kinds.append("photo")
    if inbound.get("audio_url") and "voice note" not in kinds:
        kinds.append("voice note")
    if kinds:
        parts.append("(" + ", ".join(kinds) + ")")
    return " ".join(parts) or "(empty message)"


def log_inbound(inbound: dict, *, repo: Optional[Repository] = None) -> dict:
    """Persist a Twilio inbound message so the chart shows what the patient sent.

    Uses the Twilio MessageSid as the primary key so webhook retries do not
    duplicate the same receive.
    """
    store = repo or get_repo()
    phone = inbound.get("phone_number") or ""
    patient = store.get_patient_by_phone(phone) if phone else None
    media = inbound.get("image_url") or inbound.get("audio_url")
    record = {
        "id": inbound.get("message_sid") or f"wa-in-{uuid4().hex[:10]}",
        "patient_id": patient.patient_id if patient else None,
        "phone_number": phone,
        "direction": "IN",
        "content": inbound_content(inbound),
        "language": patient.preferred_language if patient else "",
        "media_url": media,
    }
    store.insert_message(
        record["id"],
        patient_id=record["patient_id"],
        phone_number=phone,
        direction="IN",
        content=record["content"],
        language=record["language"],
        media_url=media,
    )
    return record


def parse_twilio_inbound(form: dict) -> dict:
    """Normalize a Twilio WhatsApp webhook form payload.

    A single WhatsApp message can carry several attachments — a glucometer photo and
    a voice note together is the common case — so every MediaUrlN is collected, not
    just the first. `image_url` and `audio_url` hold the first of each kind.
    """
    from_number = (form.get("From") or "").replace("whatsapp:", "")

    media: list[dict] = []
    try:
        count = int(form.get("NumMedia") or 0)
    except (TypeError, ValueError):
        count = 0
    # Fall back to scanning keys when NumMedia is absent or unparseable.
    indexes = range(count) if count else range(10)
    for i in indexes:
        url = form.get(f"MediaUrl{i}")
        if not url:
            if count:
                continue
            break
        media.append({"url": url, "content_type": form.get(f"MediaContentType{i}") or ""})

    first_image = next((m["url"] for m in media if m["content_type"].startswith("image/")), None)
    first_audio = next((m["url"] for m in media if m["content_type"].startswith("audio/")), None)

    return {
        "phone_number": from_number,
        "text": form.get("Body") or "",
        "media": media,
        "image_url": first_image,
        "audio_url": first_audio,
        "message_sid": form.get("MessageSid") or "",
    }


def validate_twilio_signature(signature: str, url: str, form: dict) -> bool:
    """Verify a webhook really came from Twilio.

    Twilio signs the exact URL it posted to. Behind ngrok, Render or any TLS
    terminator the app usually sees a different scheme or host than the caller did,
    so several plausible URLs are tried. Each still has to produce a matching HMAC
    from the auth token, so this widens the URL guess, not the trust boundary.
    """
    settings = get_settings()
    if not signature or not settings.twilio_auth_token:
        return False

    from twilio.request_validator import RequestValidator

    validator = RequestValidator(settings.twilio_auth_token)
    candidates = [url]
    if url.startswith("http://"):
        candidates.append("https://" + url[len("http://") :])
    configured = settings.webhook_url
    if configured not in candidates:
        candidates.append(configured)

    return any(validator.validate(candidate, form, signature) for candidate in candidates)


def download_media(url: str, content_type: str = "") -> Optional[str]:
    """Fetch a Twilio-hosted attachment to local disk and return its path.

    Twilio media URLs need HTTP basic auth, and the transcription and vision steps
    both read from the filesystem, so an undownloaded URL would silently yield
    nothing at all.
    """
    settings = get_settings()
    if not settings.twilio_enabled:
        logger.warning("Cannot fetch %s without Twilio credentials.", url)
        return None

    suffix = _EXTENSIONS.get(content_type) or mimetypes.guess_extension(content_type or "") or ""
    destination = settings.media_dir / f"wa-{uuid4().hex[:12]}{suffix}"
    try:
        response = httpx.get(
            url,
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            follow_redirects=True,
            timeout=30,
        )
        response.raise_for_status()
        destination.write_bytes(response.content)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch WhatsApp media %s: %s", url, exc)
        return None
    return str(destination)


def fetch_inbound_media(inbound: dict) -> dict:
    """Replace remote media URLs on a parsed payload with local file paths."""
    resolved = dict(inbound)
    for key, prefix in (("image_url", "image/"), ("audio_url", "audio/")):
        remote = inbound.get(key)
        if not remote:
            continue
        content_type = next(
            (m["content_type"] for m in inbound.get("media", []) if m["url"] == remote),
            prefix,
        )
        local = download_media(remote, content_type)
        resolved[key] = local or None
    return resolved
