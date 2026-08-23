"""End-to-end tests for the LangGraph ingress pipeline."""

import pytest

from app.agents import graph as graph_module
from app.agents.graph import dispatch_ticket, run_ingress_graph
from app.integrations import twilio_wa
from app.models.triage import ActionStatus, PriorityLevel, TicketType


@pytest.fixture(autouse=True)
def wire_repo(monkeypatch, seeded_repo):
    monkeypatch.setattr(graph_module, "_repo", lambda: seeded_repo)
    monkeypatch.setattr(twilio_wa, "OUTBOX", [])
    return seeded_repo


def test_p1_escalation_creates_pending_ticket(wire_repo):
    result = run_ingress_graph(
        phone_number="+919811000001",
        raw_text="Khane ke baad sugar 245 hai, thodi ghabrahat ho rahi hai",
    )
    assert result["priority"] == PriorityLevel.P1_ESCALATION.value
    ticket = wire_repo.get_ticket(result["ticket_id"])
    assert ticket.status == ActionStatus.PENDING
    assert ticket.ticket_type == TicketType.INGRESS
    assert ticket.drafted_response


def test_p1_does_not_auto_send(wire_repo):
    run_ingress_graph(phone_number="+919811000001", raw_text="sugar 245 hai, ghabrahat")
    assert twilio_wa.OUTBOX == [], "P1 must wait for human approval before any WhatsApp send"


def test_p0_auto_dispatches_and_alarms(wire_repo):
    result = run_ingress_graph(phone_number="+919820000010", raw_text="sugar 48, feeling very shaky")
    assert result["priority"] == PriorityLevel.P0_CRITICAL
    assert result["auto_dispatched"] is True
    assert len(twilio_wa.OUTBOX) == 1
    ticket = wire_repo.get_ticket(result["ticket_id"])
    assert ticket.ticket_type == TicketType.EMERGENCY
    assert ticket.status == ActionStatus.AUTO_DISPATCHED
    assert ticket.dispatched_message


def test_p2_routine_logs_without_ticket(wire_repo):
    result = run_ingress_graph(phone_number="+919447000009", raw_text="fasting 105 today")
    assert result["priority"] == PriorityLevel.P2_ROUTINE
    assert result["ticket_id"] is None
    assert result["skipped_ticket"] is True


def test_p3_unclear_creates_clarification_ticket(wire_repo):
    result = run_ingress_graph(phone_number="+919825000005", raw_text="machine E-1 error")
    assert result["priority"] == PriorityLevel.P3_UNCLEAR
    ticket = wire_repo.get_ticket(result["ticket_id"])
    assert "photo" in ticket.drafted_response.lower() or "number" in ticket.drafted_response.lower()


def test_reading_is_persisted_to_vitals(wire_repo):
    before = len(wire_repo.list_vitals("P-1009"))
    run_ingress_graph(phone_number="+919447000009", raw_text="fasting 105 today")
    after = wire_repo.list_vitals("P-1009")
    assert len(after) == before + 1
    assert after[-1].blood_glucose_mg_dl == 105


def test_unknown_phone_reports_error_and_writes_nothing(wire_repo):
    tickets_before = len(wire_repo.list_tickets())
    result = run_ingress_graph(phone_number="+910000000000", raw_text="sugar 245")
    assert result.get("error")
    assert len(wire_repo.list_tickets()) == tickets_before


def test_localized_draft_uses_patient_language(wire_repo):
    result = run_ingress_graph(phone_number="+919811000001", raw_text="sugar 245 hai, ghabrahat")
    ticket = wire_repo.get_ticket(result["ticket_id"])
    assert ticket.drafted_response_localized
    assert ticket.drafted_response_localized != ticket.drafted_response


def test_dispatch_sends_and_marks_approved(wire_repo):
    result = run_ingress_graph(phone_number="+919811000001", raw_text="sugar 245 hai, ghabrahat")
    ticket = dispatch_ticket(result["ticket_id"], reviewer="Dr. Rao", repo=wire_repo)
    assert ticket.status == ActionStatus.APPROVED
    assert ticket.reviewed_by == "Dr. Rao"
    assert len(twilio_wa.OUTBOX) == 1


def test_dispatch_honours_clinician_edits(wire_repo):
    result = run_ingress_graph(phone_number="+919811000001", raw_text="sugar 245 hai, ghabrahat")
    edited = "Please come to the clinic at 9 am tomorrow."
    ticket = dispatch_ticket(result["ticket_id"], edited_english=edited, repo=wire_repo)
    assert ticket.drafted_response == edited
    assert edited in twilio_wa.OUTBOX[0]["body"] or ticket.dispatched_message


def test_dispatch_unknown_ticket_returns_none(wire_repo):
    assert dispatch_ticket("T-nope", repo=wire_repo) is None


def test_multimodal_photo_plus_voice(wire_repo, tmp_path):
    from app.simulator.mock_ingress import render_glucometer

    image = render_glucometer(tmp_path / "glucometer_262.png", 262)
    result = run_ingress_graph(
        phone_number="+919811000001",
        raw_text="khane ke baad, thodi ghabrahat",
        image_url=str(image),
    )
    assert result["extracted"]["blood_glucose_mg_dl"] == 262
    assert result["extracted"]["modality"] == "multimodal"
