"""Derived clinical metrics for the care-team roster and patient detail views."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from app.db.database import Repository
from app.models.patient import PatientProfile
from app.models.triage import ActionStatus, PriorityLevel
from app.models.vitals import ReadingContext, VitalsLog

HYPO_THRESHOLD = 70.0
CONTROL_GOOD = "In range"
CONTROL_WATCH = "Watch"
CONTROL_ACTION = "Needs action"
CONTROL_SILENT = "No recent data"


def _aware(ts: Optional[datetime]) -> Optional[datetime]:
    if ts is None:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def days_since(ts: Optional[datetime]) -> Optional[int]:
    ts = _aware(ts)
    if ts is None:
        return None
    return max(0, int((datetime.now(timezone.utc) - ts).total_seconds() // 86400))


def in_target(patient: PatientProfile, log: VitalsLog) -> Optional[bool]:
    value = log.blood_glucose_mg_dl
    if value is None:
        return None
    if log.reading_context == ReadingContext.FASTING:
        return patient.target_fasting_min <= value <= patient.target_fasting_max
    if log.reading_context == ReadingContext.POST_PRANDIAL:
        return value <= patient.target_pp_max
    return patient.target_fasting_min <= value <= patient.target_pp_max


@dataclass
class PatientSummary:
    patient: PatientProfile
    # (mg/dL, reading context) for the window, oldest first — drives the corridor trace.
    recent_readings: list[tuple[float, str]]
    last_value: Optional[float]
    last_context: Optional[str]
    last_context_key: Optional[str]
    last_reading_at: Optional[datetime]
    days_quiet: Optional[int]
    readings_14d: int
    time_in_range: Optional[float]
    mean_14d: Optional[float]
    hypo_events_14d: int
    hba1c: Optional[float]
    hba1c_days: Optional[int]
    open_alerts: int
    highest_priority: Optional[PriorityLevel]
    overdue_milestones: int
    control_status: str

    @property
    def needs_attention(self) -> bool:
        return self.control_status in (CONTROL_ACTION, CONTROL_SILENT) or self.open_alerts > 0


def summarize_patient(
    repo: Repository,
    patient: PatientProfile,
    *,
    window_days: int = 14,
) -> PatientSummary:
    vitals = [v for v in repo.list_vitals(patient.patient_id) if v.blood_glucose_mg_dl is not None]
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    recent = [v for v in vitals if (_aware(v.timestamp) or cutoff) >= cutoff]

    last = vitals[-1] if vitals else None
    in_range_flags = [in_target(patient, v) for v in recent]
    in_range_flags = [f for f in in_range_flags if f is not None]
    tir = round(100 * sum(in_range_flags) / len(in_range_flags), 1) if in_range_flags else None
    mean = round(sum(v.blood_glucose_mg_dl for v in recent) / len(recent)) if recent else None
    hypos = sum(1 for v in recent if v.blood_glucose_mg_dl < HYPO_THRESHOLD)

    open_tickets = [
        t
        for t in repo.list_tickets()
        if t.patient_id == patient.patient_id
        and t.status in {ActionStatus.PENDING, ActionStatus.AUTO_DISPATCHED}
    ]
    priorities = [t.priority for t in open_tickets]
    highest = None
    for level in (
        PriorityLevel.P0_CRITICAL,
        PriorityLevel.P1_ESCALATION,
        PriorityLevel.P3_UNCLEAR,
        PriorityLevel.P2_ROUTINE,
    ):
        if level in priorities:
            highest = level
            break

    overdue = sum(1 for p in repo.list_care_plans(patient.patient_id) if p.status.value == "OVERDUE")
    quiet = days_since(last.timestamp if last else patient.last_log_timestamp)

    return PatientSummary(
        patient=patient,
        recent_readings=[(v.blood_glucose_mg_dl, v.reading_context.value) for v in recent],
        last_value=last.blood_glucose_mg_dl if last else None,
        last_context=last.reading_context.value.replace("_", " ").title() if last else None,
        last_context_key=last.reading_context.value if last else None,
        last_reading_at=_aware(last.timestamp) if last else None,
        days_quiet=quiet,
        readings_14d=len(recent),
        time_in_range=tir,
        mean_14d=mean,
        hypo_events_14d=hypos,
        hba1c=patient.last_hba1c_value,
        hba1c_days=days_since(patient.last_hba1c_date),
        open_alerts=len(open_tickets),
        highest_priority=highest,
        overdue_milestones=overdue,
        control_status=_control_status(quiet, tir, hypos, highest),
    )


def _control_status(
    quiet: Optional[int],
    tir: Optional[float],
    hypos: int,
    highest: Optional[PriorityLevel],
) -> str:
    if highest == PriorityLevel.P0_CRITICAL or hypos >= 2:
        return CONTROL_ACTION
    if quiet is None or quiet >= 7:
        return CONTROL_SILENT
    if tir is None:
        return CONTROL_SILENT
    if tir < 50 or highest == PriorityLevel.P1_ESCALATION:
        return CONTROL_ACTION
    if tir < 70:
        return CONTROL_WATCH
    return CONTROL_GOOD


def summarize_panel(repo: Repository, window_days: int = 14) -> list[PatientSummary]:
    return [summarize_patient(repo, p, window_days=window_days) for p in repo.list_patients()]


def panel_totals(summaries: Sequence[PatientSummary]) -> dict[str, int]:
    return {
        "total": len(summaries),
        "needs_action": sum(1 for s in summaries if s.control_status == CONTROL_ACTION),
        "watch": sum(1 for s in summaries if s.control_status == CONTROL_WATCH),
        "silent": sum(1 for s in summaries if s.control_status == CONTROL_SILENT),
        "in_range": sum(1 for s in summaries if s.control_status == CONTROL_GOOD),
        "open_alerts": sum(s.open_alerts for s in summaries),
    }
