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
