import pytest

from app.integrations import twilio_wa
from app.integrations.sarvam import SarvamClient
from app.integrations.twilio_wa import WhatsAppGateway, parse_twilio_inbound


@pytest.fixture(autouse=True)
def clean_outbox(monkeypatch):
    monkeypatch.setattr(twilio_wa, "OUTBOX", [])


def test_send_records_message_in_emr(repo):
    from app.models.patient import PatientProfile

    repo.upsert_patient(
        PatientProfile(patient_id="P-1", full_name="Test", phone_number="+919811000001")
    )
    gateway = WhatsAppGateway(repo)
    record = gateway.send_text("+919811000001", "hello", patient_id="P-1")
    assert record["live"] is False
    messages = repo.list_messages("P-1")
    assert len(messages) == 1
    assert messages[0]["direction"] == "OUT"


def test_send_falls_back_to_content_template(repo, monkeypatch):
    from types import SimpleNamespace

    from app.models.patient import PatientProfile

    calls = []

    class FakeMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            if "body" in kwargs:
                raise RuntimeError("63016 freeform not allowed")
            return SimpleNamespace(sid="SMtemplate")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.messages = FakeMessages()

    settings = SimpleNamespace(
        twilio_enabled=True,
        twilio_account_sid="ACtest",
        twilio_auth_token="token",
        twilio_whatsapp_from="whatsapp:+10000000000",
        twilio_content_sid="HXtemplate",
    )
    monkeypatch.setattr("app.integrations.twilio_wa.get_settings", lambda: settings)
    monkeypatch.setattr("twilio.rest.Client", FakeClient)

    repo.upsert_patient(
        PatientProfile(patient_id="P-1", full_name="Test", phone_number="+919821487690")
    )
    record = WhatsAppGateway(repo).send_text("+919821487690", "hello", patient_id="P-1")
    assert record["live"] is True
    assert record["id"] == "SMtemplate"
    assert calls[0]["body"] == "hello"
    assert calls[1]["content_sid"] == "HXtemplate"


def test_outbox_is_readable_after_send(repo):
    from app.models.patient import PatientProfile

    repo.upsert_patient(
        PatientProfile(patient_id="P-1", full_name="Test", phone_number="+919811000001")
    )
    gateway = WhatsAppGateway(repo)
    gateway.send_text("+919811000001", "first", patient_id="P-1")
    gateway.send_text("+919811000001", "second", patient_id="P-1")
    bodies = [m["body"] for m in gateway.recent_outbox()]
    assert bodies == ["second", "first"]


def test_log_inbound_writes_registered_messages_to_the_chart(repo):
    from app.integrations.twilio_wa import log_inbound
    from app.models.patient import PatientProfile

    repo.upsert_patient(
        PatientProfile(patient_id="P-1", full_name="Test", phone_number="+919821487690")
    )
    record = log_inbound(
        {
            "phone_number": "+919821487690",
            "text": "sugar 132",
            "message_sid": "SM-in-1",
            "image_url": None,
            "audio_url": None,
            "media": [],
        },
        repo=repo,
    )
    assert record["patient_id"] == "P-1"
    messages = repo.list_messages("P-1")
    assert messages[0]["direction"] == "IN"
    assert messages[0]["content"] == "sugar 132"


def test_log_inbound_keeps_unknown_numbers_and_notes_attachments(repo):
    from app.integrations.twilio_wa import log_inbound

    log_inbound(
        {
            "phone_number": "+919999999999",
            "text": "",
            "message_sid": "SM-in-2",
            "image_url": "https://api.twilio.com/media/img",
            "audio_url": None,
            "media": [{"url": "https://api.twilio.com/media/img", "content_type": "image/jpeg"}],
        },
        repo=repo,
    )
    rows = repo.recent_messages(direction="IN")
    assert rows[0]["patient_id"] is None
    assert "photo" in rows[0]["content"]


def test_log_inbound_is_idempotent_on_the_same_message_sid(repo):
    from app.integrations.twilio_wa import log_inbound

    payload = {
        "phone_number": "+919999999998",
        "text": "hello",
        "message_sid": "SM-dup",
        "media": [],
    }
    log_inbound(payload, repo=repo)
    log_inbound(payload, repo=repo)
    assert len(repo.recent_messages(direction="IN")) == 1


@pytest.mark.parametrize(
    "form,expected",
    [
        (
            {"From": "whatsapp:+919821487690", "Body": "sugar 110"},
            {"phone_number": "+919821487690", "text": "sugar 110", "image_url": None, "audio_url": None},
        ),
        (
            {
                "From": "whatsapp:+919821487690",
                "Body": "",
                "MediaUrl0": "https://api.twilio.com/media/img",
                "MediaContentType0": "image/jpeg",
            },
            {"phone_number": "+919821487690", "image_url": "https://api.twilio.com/media/img"},
        ),
        (
            {
                "From": "whatsapp:+919821487690",
                "MediaUrl0": "https://api.twilio.com/media/aud",
                "MediaContentType0": "audio/ogg",
            },
            {"audio_url": "https://api.twilio.com/media/aud", "image_url": None},
        ),
    ],
)
def test_parse_twilio_inbound(form, expected):
    parsed = parse_twilio_inbound(form)
    for key, value in expected.items():
        assert parsed[key] == value


def test_sarvam_offline_translation_is_language_specific():
    client = SarvamClient()
    english = "Your reading is above target."
    assert client.translate_from_english(english, "en") == english
    hindi = client.translate_from_english(english, "hi")
    marathi = client.translate_from_english(english, "mr")
    assert hindi != english
    assert hindi != marathi


def test_sarvam_english_passthrough_does_not_mangle_text():
    client = SarvamClient()
    assert client.translate_to_english("sugar is 110", "en") == "sugar is 110"


def test_sarvam_transcribe_without_audio_returns_empty():
    assert SarvamClient().transcribe(None) == ""
