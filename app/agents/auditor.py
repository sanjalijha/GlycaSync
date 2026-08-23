"""Agent 3 — proactive EMR auditor for overdue labs, consults, and logging drop-offs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.agents.synthesizer import outreach_consult_draft, outreach_dropoff_draft, outreach_hba1c_draft
from app.db.database import Repository, get_repo
from app.models.care_plan import MilestoneStatus
from app.models.patient import PatientProfile
from app.models.triage import ActionStatus, PriorityLevel, TicketType, TriageTicket
from app.models.vitals import ExtractedObservation, utcnow

HBA1C_OVERDUE_DAYS = 90
CONSULT_OVERDUE_DAYS = 90
DROPOFF_DAYS = 4


def _days_since(ts: Optional[datetime]) -> Optional[int]:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max(0, int((datetime.now(timezone.utc) - ts).total_seconds() // 86400))


def _open_outreach_reasons(repo: Repository, patient_id: str) -> set[str]:
    reasons = set()
    for ticket in repo.list_tickets(status=ActionStatus.PENDING.value, ticket_type=TicketType.OUTREACH.value):
        if ticket.patient_id == patient_id:
            reasons.add(ticket.triage_reason)
    return reasons


def _make_ticket(
    patient: PatientProfile,
    reason: str,
    english: str,
    localized: str,
    notes: str,
) -> TriageTicket:
    return TriageTicket(
        ticket_id=f"T-AUD-{uuid4().hex[:8]}",
        patient_id=patient.patient_id,
        priority=PriorityLevel.P1_ESCALATION,
        extracted_data=ExtractedObservation(
            patient_id=patient.patient_id,
            confidence_score=1.0,
            extraction_notes=notes,
            modality="system",
        ),
        triage_reason=reason,
        drafted_response=english,
        drafted_response_localized=localized,
        status=ActionStatus.PENDING,
        ticket_type=TicketType.OUTREACH,
        created_at=utcnow(),
    )


def audit_emr(repo: Optional[Repository] = None) -> list[TriageTicket]:
    """Sweep patients + care plans. Insert new outreach tickets; skip duplicates."""
    repo = repo or get_repo()
    created: list[TriageTicket] = []

    for patient in repo.list_patients():
        existing = _open_outreach_reasons(repo, patient.patient_id)
        hba1c_days = _days_since(patient.last_hba1c_date)
        if hba1c_days is not None and hba1c_days > HBA1C_OVERDUE_DAYS:
            reason = (
                f"HbA1c last recorded {hba1c_days} days ago "
                f"({patient.last_hba1c_value if patient.last_hba1c_value else 'unknown'}%). "
                f"Cadence is {HBA1C_OVERDUE_DAYS} days."
            )
            if reason not in existing:
                en, loc = outreach_hba1c_draft(patient, hba1c_days)
                ticket = _make_ticket(patient, reason, en, loc, "Auditor: overdue HbA1c")
                repo.insert_ticket(ticket)
                created.append(ticket)

        consult_days = _days_since(patient.last_consult_date)
        if consult_days is not None and consult_days > CONSULT_OVERDUE_DAYS:
            reason = f"Physician follow-up overdue by {consult_days} days."
            if reason not in existing:
                en, loc = outreach_consult_draft(patient, consult_days)
                ticket = _make_ticket(patient, reason, en, loc, "Auditor: overdue consult")
                repo.insert_ticket(ticket)
                created.append(ticket)

        quiet = _days_since(patient.last_log_timestamp)
        if patient.insulin_dependent and quiet is not None and quiet >= DROPOFF_DAYS:
            reason = (
                f"No glucose logs for {quiet} days. Patient is insulin-dependent "
                f"(drop-off threshold: {DROPOFF_DAYS} days)."
            )
            if reason not in existing:
                en, loc = outreach_dropoff_draft(patient, quiet)
                ticket = _make_ticket(patient, reason, en, loc, "Auditor: logging drop-off")
                repo.insert_ticket(ticket)
                created.append(ticket)

    # Sync care-plan statuses
    now = datetime.now(timezone.utc)
    for plan in repo.list_care_plans():
        if plan.status == MilestoneStatus.COMPLETED:
            continue
        target = plan.target_date
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        if target < now and plan.status != MilestoneStatus.OVERDUE:
            plan.status = MilestoneStatus.OVERDUE
            repo.upsert_care_plan(plan)

    return created


if __name__ == "__main__":
    tickets = audit_emr()
    print(f"Auditor created {len(tickets)} outreach ticket(s).")
    for t in tickets:
        print(f"  {t.ticket_id} {t.patient_id}: {t.triage_reason}")
