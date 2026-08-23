"""Agent 4 — drafts a reply for the specific clinical situation, then localizes it."""

from __future__ import annotations

from app.agents.triage import HYPO_ALERT, TriageResult
from app.integrations.sarvam import SarvamClient
from app.models.patient import PatientProfile
from app.models.triage import PriorityLevel, TicketType
from app.models.vitals import ExtractedObservation, ReadingContext

SARVAM = SarvamClient()

SIGN_OFF = "Your care team is reviewing this. Do not change a dose until they confirm."


def synthesize_reply(
    patient: PatientProfile,
    obs: ExtractedObservation,
    triage: TriageResult,
    ticket_type: TicketType = TicketType.INGRESS,
) -> tuple[str, str]:
    english = _english_draft(patient, obs, triage, ticket_type)
    localized = SARVAM.translate_from_english(english, patient.preferred_language)
    return english, localized


def _first_name(patient: PatientProfile) -> str:
    return patient.full_name.split()[0]


def _context_phrase(obs: ExtractedObservation) -> str:
    return {
        ReadingContext.FASTING: "fasting",
        ReadingContext.POST_PRANDIAL: "after a meal",
        ReadingContext.BEDTIME: "at bedtime",
        ReadingContext.RANDOM: "random",
    }.get(obs.reading_context, obs.reading_context.value.replace("_", " ").lower())


def _symptoms(obs: ExtractedObservation) -> str:
    if not obs.symptoms:
        return ""
    return ", ".join(s.replace("_", " ") for s in obs.symptoms)


def _english_draft(
    patient: PatientProfile,
    obs: ExtractedObservation,
    triage: TriageResult,
    ticket_type: TicketType,
) -> str:
    if ticket_type == TicketType.OUTREACH:
        return triage.reason

    if triage.priority == PriorityLevel.P0_CRITICAL:
        return triage.emergency_english

    if triage.priority == PriorityLevel.P3_UNCLEAR:
        return _unclear(patient, obs)

    if triage.priority == PriorityLevel.P1_ESCALATION:
        return _escalation(patient, obs)

    return _in_range(patient, obs)


def _unclear(patient: PatientProfile, obs: ExtractedObservation) -> str:
    name = _first_name(patient)
    if obs.device_error:
        return (
            f"{name} ji, the meter is showing {obs.device_error}, so we cannot log a number. "
            "Wash and dry your hands, use a new strip, and send a photo of the screen "
            "that shows the digits — or type the number if you can read it."
        )
    return (
        f"{name} ji, we could not read a sugar number from that message. "
        "Type it like 'fasting 118' or send a sharper photo of the meter screen."
    )


def _escalation(patient: PatientProfile, obs: ExtractedObservation) -> str:
    name = _first_name(patient)
    value = obs.blood_glucose_mg_dl
    when = _context_phrase(obs)
    felt = _symptoms(obs)
    felt_bit = f" You also mentioned {felt}." if felt else ""

    if value is not None and value < HYPO_ALERT:
        return (
            f"{name} ji, {value:.0f} mg/dL {when} is a low.{felt_bit} "
            "Take 15 grams of fast-acting sugar now (half a cup of juice or three glucose tablets), "
            "sit down, and recheck in 15 minutes. Send that next number. "
            "If you feel confused or cannot swallow, ask someone with you to call 108."
        )

    ceiling = (
        patient.target_fasting_max
        if obs.reading_context == ReadingContext.FASTING
        else patient.target_pp_max
    )
    if obs.reading_context == ReadingContext.FASTING:
        next_step = (
            "Eat your usual breakfast, take your usual morning medicines, and send the "
            "reading two hours after that meal."
        )
    elif obs.reading_context == ReadingContext.POST_PRANDIAL:
        next_step = (
            "Do not take an extra insulin shot or an extra tablet. Sip water, walk indoors "
            "for 10–15 minutes if you feel steady, and send tonight's bedtime reading."
        )
    else:
        next_step = (
            "Sip water and rest. Send your next fasting reading tomorrow morning "
            "before breakfast."
        )

    insulin_bit = (
        " Because you are on insulin, do not add a correction dose until the team confirms."
        if patient.insulin_dependent
        else " Stay on your usual tablets unless the team tells you otherwise."
    )
    return (
        f"{name} ji, {value:.0f} mg/dL {when} is above your target of {ceiling:.0f}.{felt_bit}"
        f"{insulin_bit} {next_step} {SIGN_OFF} "
        "Call 108 if chest pain, confusion, or fainting starts."
    )


def _in_range(patient: PatientProfile, obs: ExtractedObservation) -> str:
    name = _first_name(patient)
    value = obs.blood_glucose_mg_dl
    when = _context_phrase(obs)
    return (
        f"{name} ji, {value:.0f} mg/dL {when} is inside your corridor "
        f"({patient.target_fasting_min:.0f}–{patient.target_fasting_max:.0f} fasting, "
        f"under {patient.target_pp_max:.0f} after a meal). Logged. "
        "Keep the same meals and medicines."
    )


def outreach_hba1c_draft(patient: PatientProfile, days_overdue: int) -> tuple[str, str]:
    name = _first_name(patient)
    last = f"{patient.last_hba1c_value:g}%" if patient.last_hba1c_value else "not on file"
    english = (
        f"{name} ji, your last HbA1c was {last}, recorded {days_overdue} days ago. "
        "This test shows three-month control and is due every 90 days. "
        "Get it at your usual lab this week and WhatsApp a photo of the report "
        "so we can see whether your current plan is holding."
    )
    return english, SARVAM.translate_from_english(english, patient.preferred_language)


def outreach_dropoff_draft(patient: PatientProfile, quiet_days: int) -> tuple[str, str]:
    name = _first_name(patient)
    english = (
        f"{name} ji, we have had no sugar readings for {quiet_days} days. "
        "You are on insulin, so a silent meter means we cannot see a low coming. "
        "Send today's fasting number now — type it or photograph the meter. "
        "If the meter is broken, reply METER and we will work out a replacement."
    )
    return english, SARVAM.translate_from_english(english, patient.preferred_language)


def outreach_consult_draft(patient: PatientProfile, days_overdue: int) -> tuple[str, str]:
    name = _first_name(patient)
    english = (
        f"{name} ji, it has been {days_overdue} days since your last clinic visit. "
        "Before the doctor reviews your plan they need a current picture — "
        "send the next three fasting readings and one after-meal reading this week. "
        "If a reading is under 70 or over 250, send it immediately."
    )
    return english, SARVAM.translate_from_english(english, patient.preferred_language)
