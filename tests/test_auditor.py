from datetime import datetime, timedelta, timezone

from app.agents.auditor import audit_emr
from app.models.patient import PatientProfile
from app.models.triage import ActionStatus, TicketType


def days_ago(n: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n)


def test_flags_overdue_hba1c(repo):
    repo.upsert_patient(
        PatientProfile(
            patient_id="P-A",
            full_name="Overdue Lab",
            phone_number="+919000000001",
            last_hba1c_date=days_ago(120),
            last_hba1c_value=8.1,
            last_consult_date=days_ago(10),
            last_log_timestamp=days_ago(1),
        )
    )
    created = audit_emr(repo)
    assert any("HbA1c" in t.triage_reason for t in created)
    hba1c = next(t for t in created if "HbA1c" in t.triage_reason)
    assert "report" in hba1c.drafted_response.lower()
    assert "yes" not in hba1c.drafted_response.lower()


def test_recent_hba1c_not_flagged(repo):
    repo.upsert_patient(
        PatientProfile(
            patient_id="P-B",
            full_name="Recent Lab",
            phone_number="+919000000002",
            last_hba1c_date=days_ago(30),
            last_consult_date=days_ago(10),
            last_log_timestamp=days_ago(1),
        )
    )
    assert audit_emr(repo) == []


def test_flags_logging_dropoff_only_for_insulin_patients(repo):
    repo.upsert_patient(
        PatientProfile(
            patient_id="P-INS",
            full_name="Insulin User",
            phone_number="+919000000003",
            insulin_dependent=True,
            last_hba1c_date=days_ago(10),
            last_consult_date=days_ago(10),
            last_log_timestamp=days_ago(7),
        )
    )
    repo.upsert_patient(
        PatientProfile(
            patient_id="P-OAD",
            full_name="Tablet User",
            phone_number="+919000000004",
            insulin_dependent=False,
            last_hba1c_date=days_ago(10),
            last_consult_date=days_ago(10),
            last_log_timestamp=days_ago(7),
        )
    )
    created = audit_emr(repo)
    flagged = {t.patient_id for t in created}
    assert "P-INS" in flagged
    assert "P-OAD" not in flagged


def test_flags_overdue_consult(repo):
    repo.upsert_patient(
        PatientProfile(
            patient_id="P-C",
            full_name="Overdue Consult",
            phone_number="+919000000005",
            last_hba1c_date=days_ago(10),
            last_consult_date=days_ago(200),
            last_log_timestamp=days_ago(1),
        )
    )
    created = audit_emr(repo)
    assert any("follow-up" in t.triage_reason for t in created)


def test_outreach_tickets_are_pending_and_typed(repo):
    repo.upsert_patient(
        PatientProfile(
            patient_id="P-D",
            full_name="Needs Outreach",
            phone_number="+919000000006",
            last_hba1c_date=days_ago(200),
            last_consult_date=days_ago(10),
            last_log_timestamp=days_ago(1),
        )
    )
    created = audit_emr(repo)
    assert created
    for ticket in created:
        assert ticket.status == ActionStatus.PENDING
        assert ticket.ticket_type == TicketType.OUTREACH
        assert ticket.drafted_response


def test_repeated_sweeps_do_not_duplicate_tickets(repo):
    repo.upsert_patient(
        PatientProfile(
            patient_id="P-E",
            full_name="Sweep Twice",
            phone_number="+919000000007",
            last_hba1c_date=days_ago(200),
            last_consult_date=days_ago(200),
            insulin_dependent=True,
            last_log_timestamp=days_ago(30),
        )
    )
    first = audit_emr(repo)
    second = audit_emr(repo)
    assert len(first) == 3
    assert second == [], "a second sweep must not re-queue the same outreach"


def test_sweep_marks_past_milestones_overdue(seeded_repo):
    from app.models.care_plan import MilestoneStatus

    audit_emr(seeded_repo)
    now = datetime.now(timezone.utc)
    for plan in seeded_repo.list_care_plans():
        target = plan.target_date
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        if target < now and plan.status != MilestoneStatus.COMPLETED:
            assert plan.status == MilestoneStatus.OVERDUE
