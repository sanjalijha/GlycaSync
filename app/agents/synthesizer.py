"""Agent 4 — guardrailed communication synthesizer (English draft + localized copy)."""

from __future__ import annotations

from app.agents.triage import TriageResult
from app.integrations.sarvam import SarvamClient
from app.models.patient import PatientProfile
from app.models.triage import PriorityLevel, TicketType
from app.models.vitals import ExtractedObservation

SARVAM = SarvamClient()


def synthesize_reply(
    patient: PatientProfile,
    obs: ExtractedObservation,
    triage: TriageResult,
    ticket_type: TicketType = TicketType.INGRESS,
) -> tuple[str, str]:
    english = _english_draft(patient, obs, triage, ticket_type)
    localized = SARVAM.translate_from_english(english, patient.preferred_language)
    return english, localized


def _english_draft(
    patient: PatientProfile,
    obs: ExtractedObservation,
    triage: TriageResult,
    ticket_type: TicketType,
) -> str:
    name = patient.full_name.split()[0]
    value = obs.blood_glucose_mg_dl
    ctx = obs.reading_context.value.replace("_", " ").title()

    if ticket_type == TicketType.OUTREACH:
        return (
            f"{name} ji, this is {patient.city} care coordination. "
            f"{triage.reason} Reply YES to book a home collection / tele-consult slot, or CALL if you prefer a phone visit."
        )

    if triage.priority == PriorityLevel.P0_CRITICAL:
        return triage.emergency_english

    if triage.priority == PriorityLevel.P3_UNCLEAR:
        if obs.device_error:
            return (
                f"{name} ji, the glucometer photo looks like a {obs.device_error} error. "
                "Please use a new strip, wash and dry your hands, and send a clear photo of the number screen."
            )
        return (
            f"{name} ji, we could not read a clear sugar number from your last message. "
            "Please type the number (for example: fasting 118) or send a sharper photo of the glucometer screen."
        )

    if triage.priority == PriorityLevel.P1_ESCALATION:
        symptom_bit = ""
        if obs.symptoms:
            symptom_bit = f" along with {', '.join(s.replace('_', ' ') for s in obs.symptoms)}"
        return (
            f"{name} ji — we received your {ctx.lower()} reading of {value:g} mg/dL{symptom_bit}. "
            f"Your personal target is fasting {patient.target_fasting_min:g}–{patient.target_fasting_max:g} "
            f"and post-meal under {patient.target_pp_max:g}. A coordinator will review this shortly. "
            "Please sit, sip water, and do not change insulin or tablets until we confirm. "
            "If chest pain, confusion, or fainting starts, call 108."
        )

    return (
        f"{name} ji, thank you — {ctx.lower()} {value:g} mg/dL is within your target band "
        f"({patient.target_fasting_min:g}–{patient.target_fasting_max:g} fasting / PP ≤ {patient.target_pp_max:g}). "
        "We have logged it to your record. Keep your usual meals and medicines."
    )


def outreach_hba1c_draft(patient: PatientProfile, days_overdue: int) -> tuple[str, str]:
    name = patient.full_name.split()[0]
    last = f"{patient.last_hba1c_value}%" if patient.last_hba1c_value else "your last result"
    english = (
        f"{name} ji, your HbA1c test is now overdue by about {days_overdue} days "
        f"(last recorded {last}). We can arrange home sample collection tomorrow 7–9 am. "
        "Reply YES to confirm the slot, or SEND a nearby lab name if you prefer to walk in."
    )
    return english, SARVAM.translate_from_english(english, patient.preferred_language)


def outreach_dropoff_draft(patient: PatientProfile, quiet_days: int) -> tuple[str, str]:
    name = patient.full_name.split()[0]
    english = (
        f"{name} ji, we have not received sugar readings for {quiet_days} days. "
        "Because you use insulin, a daily log keeps your plan safe. "
        "Please send tomorrow's fasting photo, or reply HELP if the meter is not working."
    )
    return english, SARVAM.translate_from_english(english, patient.preferred_language)


def outreach_consult_draft(patient: PatientProfile, days_overdue: int) -> tuple[str, str]:
    name = patient.full_name.split()[0]
    english = (
        f"{name} ji, your doctor follow-up is overdue by about {days_overdue} days. "
        "Shall we book a 10-minute tele-consult this week? Reply YES or send two time windows."
    )
    return english, SARVAM.translate_from_english(english, patient.preferred_language)
