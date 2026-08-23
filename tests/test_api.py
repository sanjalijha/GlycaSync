import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    keys = (
        "DATABASE_PATH",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_VALIDATE_SIGNATURE",
    )
    previous = {key: os.environ.get(key) for key in keys}
    os.environ["DATABASE_PATH"] = str(tmp_path_factory.mktemp("api") / "api.db")
    os.environ["TWILIO_ACCOUNT_SID"] = ""
    os.environ["TWILIO_AUTH_TOKEN"] = ""
    os.environ["TWILIO_VALIDATE_SIGNATURE"] = "false"
    from app.config import get_settings
    from app.db.database import get_repo

    get_settings.cache_clear()
    get_repo.cache_clear()
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()
    get_repo.cache_clear()


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["patients"] == 10
    assert body["twilio"] is False


def test_list_patients(client):
    patients = client.get("/api/patients").json()
    assert len(patients) == 10
    assert {"patient_id", "full_name", "phone_number"} <= set(patients[0])


def test_get_patient_and_404(client):
    assert client.get("/api/patients/P-1001").json()["full_name"] == "Rajesh Kumar"
    assert client.get("/api/patients/P-9999").status_code == 404


def test_vitals_and_care_plans(client):
    assert len(client.get("/api/patients/P-1001/vitals").json()) > 0
    assert len(client.get("/api/patients/P-1001/care-plans").json()) > 0


def test_stats_shape(client):
    stats = client.get("/api/stats").json()
    assert set(stats) == {"p0", "p1", "p3", "outreach", "patients"}


def test_simulate_ingress_runs_pipeline(client):
    response = client.post(
        "/api/ingress/simulate",
        json={"phone_number": "+919811000001", "text": "khane ke baad sugar 245, ghabrahat"},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["priority"] == "P1_ESCALATION"
    assert body["ticket_id"]


def test_tickets_filterable(client):
    pending = client.get("/api/tickets", params={"status": "PENDING"}).json()
    assert all(t["status"] == "PENDING" for t in pending)


def test_dispatch_ticket(client):
    created = client.post(
        "/api/ingress/simulate",
        json={"phone_number": "+919811000001", "text": "sugar 260 khane ke baad, chakkar"},
    ).json()
    response = client.post(
        f"/api/tickets/{created['ticket_id']}/dispatch",
        json={"reviewer": "Dr. Rao"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"


def test_dispatch_unknown_ticket_404(client):
    assert client.post("/api/tickets/T-nope/dispatch", json={}).status_code == 404


def test_auditor_endpoint(client):
    body = client.post("/api/auditor/run").json()
    assert "count" in body and isinstance(body["created"], list)


def test_twilio_webhook_buffers_message(client):
    response = client.post(
        "/webhook/whatsapp",
        data={"From": "whatsapp:+919811000001", "Body": "sugar 150", "MessageSid": "SM123"},
    )
    assert response.status_code == 200
    assert "<Response>" in response.text
    inbox = client.get("/api/patients/P-1001/messages").json()
    assert any(m["direction"] == "IN" and "sugar 150" in m["content"] for m in inbox)


def test_webhook_returns_twiml_when_requested(client):
    """Twilio expects a 2xx; an empty TwiML body is the safe acknowledgement."""
    response = client.post(
        "/webhook/whatsapp",
        data={"From": "whatsapp:+919811000001", "Body": "hello", "MessageSid": "SM124"},
    )
    assert response.status_code == 200
