from datetime import datetime, timedelta, timezone

from app.models.care_plan import CarePlanMilestone, MilestoneStatus, MilestoneType
from app.models.patient import PatientProfile
from app.models.triage import ActionStatus, PriorityLevel, TriageTicket
from app.models.vitals import ExtractedObservation, ReadingContext, VitalsLog


def make_patient(pid="P-1", phone="+919811000001") -> PatientProfile:
    return PatientProfile(
        patient_id=pid,
        full_name="Test Patient",
        phone_number=phone,
        medications=["Metformin 500 mg"],
    )


def test_patient_roundtrip_preserves_fields(repo):
    patient = make_patient()
    repo.upsert_patient(patient)
    loaded = repo.get_patient("P-1")
    assert loaded.full_name == patient.full_name
    assert loaded.medications == ["Metformin 500 mg"]
    assert loaded.target_fasting_max == 130


def test_upsert_is_idempotent(repo):
    repo.upsert_patient(make_patient())
    repo.upsert_patient(make_patient())
    assert repo.patient_count() == 1


def test_lookup_by_phone_handles_formatting(repo):
    repo.upsert_patient(make_patient(phone="+919811000001"))
    for variant in ["+919811000001", "919811000001", "9811000001", "+91 98110 00001"]:
        assert repo.get_patient_by_phone(variant) is not None, variant


def test_lookup_by_unknown_phone_returns_none(repo):
    repo.upsert_patient(make_patient(phone="+919811000001"))
    assert repo.get_patient_by_phone("+919999999999") is None


def test_reseeding_an_existing_database_replaces_it(seeded_repo):
    """Regression: force reseeding used to collide on primary keys instead of starting clean."""
    from app.db.seed_data import seed

    before = seeded_repo.patient_count()
    result = seed(repo=seeded_repo, force=True)

    assert "skipped" not in result
    assert seeded_repo.patient_count() == before
    log_ids = [v.log_id for p in seeded_repo.list_patients() for v in seeded_repo.list_vitals(p.patient_id)]
    assert len(log_ids) == len(set(log_ids))


def test_clear_empties_every_table(seeded_repo):
    seeded_repo.clear()

    assert seeded_repo.patient_count() == 0
    assert seeded_repo.list_tickets() == []
    assert seeded_repo.recent_messages(limit=5) == []


def test_seed_includes_an_open_critical_alert(seeded_repo):
    """The hypoglycemia circuit breaker must be visible on a fresh install."""
    critical = [t for t in seeded_repo.list_tickets() if t.priority == PriorityLevel.P0_CRITICAL]

    assert critical, "expected a seeded critical low"
    ticket = critical[0]
    assert ticket.status == ActionStatus.AUTO_DISPATCHED
    assert ticket.dispatched_message, "first-aid guidance should already have gone out"
    assert ticket.extracted_data.blood_glucose_mg_dl < 55


def test_short_phone_does_not_false_match(repo):
    """Regression: a truncated number must not silently resolve to a real patient."""
    repo.upsert_patient(make_patient(phone="+919811000001"))
    assert repo.get_patient_by_phone("001") is None


def test_vitals_ordered_and_update_last_log(repo):
    repo.upsert_patient(make_patient())
    now = datetime.now(timezone.utc)
    for i, value in enumerate([120, 130, 140]):
        repo.insert_vital(
            VitalsLog(
                log_id=f"obs-{i}",
                patient_id="P-1",
                timestamp=now - timedelta(days=3 - i),
                blood_glucose_mg_dl=value,
                reading_context=ReadingContext.FASTING,
                confidence_score=0.9,
            )
        )
    vitals = repo.list_vitals("P-1")
    assert [v.blood_glucose_mg_dl for v in vitals] == [120, 130, 140]
    assert repo.get_patient("P-1").last_log_timestamp is not None


def test_ticket_roundtrip_and_priority_ordering(repo):
    repo.upsert_patient(make_patient())
    for tid, priority in [
        ("T-routine", PriorityLevel.P2_ROUTINE),
        ("T-crit", PriorityLevel.P0_CRITICAL),
        ("T-unclear", PriorityLevel.P3_UNCLEAR),
        ("T-esc", PriorityLevel.P1_ESCALATION),
    ]:
        repo.insert_ticket(
            TriageTicket(
                ticket_id=tid,
                patient_id="P-1",
                priority=priority,
                extracted_data=ExtractedObservation(patient_id="P-1", confidence_score=0.9),
                triage_reason="test",
                drafted_response="draft",
            )
        )
    order = [t.ticket_id for t in repo.list_tickets()]
    assert order[:2] == ["T-crit", "T-esc"]
    assert order[2] == "T-unclear"


def test_ticket_status_update_records_reviewer(repo):
    repo.upsert_patient(make_patient())
    repo.insert_ticket(
        TriageTicket(
            ticket_id="T-1",
            patient_id="P-1",
            priority=PriorityLevel.P1_ESCALATION,
            extracted_data=ExtractedObservation(patient_id="P-1", confidence_score=0.9),
            triage_reason="test",
            drafted_response="draft",
        )
    )
    updated = repo.update_ticket("T-1", status=ActionStatus.APPROVED, reviewed_by="Dr. Rao")
    assert updated.status == ActionStatus.APPROVED
    assert updated.reviewed_by == "Dr. Rao"
    assert updated.reviewed_at is not None
    assert repo.get_ticket("T-1").status == ActionStatus.APPROVED


def test_update_missing_ticket_returns_none(repo):
    assert repo.update_ticket("nope", status=ActionStatus.APPROVED) is None


def test_care_plan_upsert_and_filter(repo):
    repo.upsert_patient(make_patient())
    plan = CarePlanMilestone(
        plan_id="cp-1",
        patient_id="P-1",
        milestone_type=MilestoneType.HBA1C,
        title="HbA1c",
        target_date=datetime.now(timezone.utc) - timedelta(days=5),
        status=MilestoneStatus.SCHEDULED,
    )
    repo.upsert_care_plan(plan)
    plan.status = MilestoneStatus.OVERDUE
    repo.upsert_care_plan(plan)
    plans = repo.list_care_plans("P-1")
    assert len(plans) == 1
    assert plans[0].status == MilestoneStatus.OVERDUE


def test_messages_are_scoped_to_patient(repo):
    repo.upsert_patient(make_patient("P-1", "+919811000001"))
    repo.upsert_patient(make_patient("P-2", "+919811000002"))
    repo.insert_message("m1", patient_id="P-1", phone_number="+919811000001", direction="OUT", content="hi")
    repo.insert_message("m2", patient_id="P-2", phone_number="+919811000002", direction="OUT", content="yo")
    assert len(repo.list_messages("P-1")) == 1


def test_dashboard_counts(seeded_repo):
    counts = seeded_repo.dashboard_counts()
    assert counts["patients"] == 10
    assert set(counts) == {"p0", "p1", "p3", "outreach", "patients"}


def test_seed_is_idempotent(seeded_repo):
    from app.db.seed_data import seed

    before = seeded_repo.patient_count()
    seed(seeded_repo)
    assert seeded_repo.patient_count() == before
