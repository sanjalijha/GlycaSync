"""Connecting Twilio, persisting credentials, and attaching a live number."""

import pytest

from app.config import get_settings, upsert_env_keys
from app.integrations.twilio_wa import (
    SANDBOX_FROM,
    connect_whatsapp,
    disconnect_whatsapp,
    normalize_e164,
    normalize_whatsapp_from,
)
from app.models.patient import PatientProfile


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    monkeypatch.setattr("app.config.ENV_PATH", env)
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_WHATSAPP_FROM", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    get_settings.cache_clear()
    yield env
    get_settings.cache_clear()
    for key in (
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_WHATSAPP_FROM",
        "PUBLIC_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_normalize_indian_mobile_to_e164():
    assert normalize_e164("9821487690") == "+919821487690"
    assert normalize_e164("+91 98214 87690") == "+919821487690"
    assert normalize_e164("whatsapp:+919821487690") == "+919821487690"
    assert normalize_e164("") == ""


def test_normalize_whatsapp_from_accepts_bare_number():
    assert normalize_whatsapp_from("+14155238886") == SANDBOX_FROM
    assert normalize_whatsapp_from(SANDBOX_FROM) == SANDBOX_FROM
    assert normalize_whatsapp_from("") == SANDBOX_FROM


def test_upsert_env_keys_keeps_comments_and_other_values(tmp_path):
    path = tmp_path / ".env"
    path.write_text("# clinic\nCLINIC_CITY=Mumbai\nTWILIO_ACCOUNT_SID=old\n", encoding="utf-8")
    upsert_env_keys({"TWILIO_ACCOUNT_SID": "ACnew", "TWILIO_AUTH_TOKEN": "secret"}, path=path)
    text = path.read_text(encoding="utf-8")
    assert "# clinic" in text
    assert "CLINIC_CITY=Mumbai" in text
    assert "TWILIO_ACCOUNT_SID=ACnew" in text
    assert "TWILIO_AUTH_TOKEN=secret" in text
    assert "old" not in text


def test_connect_whatsapp_persists_after_verify(isolated_env, monkeypatch):
    def fake_verify(sid, token):
        assert sid == "ACabc"
        assert token == "token123"
        return True, "GlycaSync"

    monkeypatch.setattr("app.integrations.twilio_wa.verify_twilio", fake_verify)
    ok, webhook = connect_whatsapp(
        account_sid="ACabc",
        auth_token="token123",
        whatsapp_from="+14155238886",
        public_base_url="https://demo.example/hook",
    )
    assert ok
    assert webhook.endswith("/webhook/whatsapp")
    settings = get_settings()
    assert settings.twilio_enabled
    assert settings.twilio_account_sid == "ACabc"
    assert "TWILIO_ACCOUNT_SID=ACabc" in isolated_env.read_text(encoding="utf-8")


def test_connect_whatsapp_refuses_bad_credentials(isolated_env, monkeypatch):
    monkeypatch.setattr(
        "app.integrations.twilio_wa.verify_twilio",
        lambda sid, token: (False, "Authenticate"),
    )
    ok, detail = connect_whatsapp(account_sid="ACbad", auth_token="nope")
    assert ok is False
    assert "Authenticate" in detail
    assert not isolated_env.exists() or "ACbad" not in isolated_env.read_text(encoding="utf-8")


def test_disconnect_clears_credentials(isolated_env, monkeypatch):
    monkeypatch.setattr("app.integrations.twilio_wa.verify_twilio", lambda *a: (True, "ok"))
    connect_whatsapp(account_sid="ACabc", auth_token="token123", verify=True)
    disconnect_whatsapp()
    assert get_settings().twilio_enabled is False


def test_set_patient_phone_rejects_a_number_already_on_another_chart(repo):
    repo.upsert_patient(PatientProfile(patient_id="P-1", full_name="A", phone_number="+919811000001"))
    repo.upsert_patient(PatientProfile(patient_id="P-2", full_name="B", phone_number="+919811000002"))
    with pytest.raises(ValueError, match="already on"):
        repo.set_patient_phone("P-2", "+919811000001")


def test_set_patient_phone_attaches_a_live_number(repo):
    repo.upsert_patient(PatientProfile(patient_id="P-1", full_name="A", phone_number="+919811000001"))
    updated = repo.set_patient_phone("P-1", "9821487690")
    assert updated.phone_number == "+919821487690"
    assert repo.get_patient_by_phone("+919821487690").patient_id == "P-1"
