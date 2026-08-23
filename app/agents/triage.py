"""Agent 2 — hybrid deterministic + contextual triage with P0 circuit breaker."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.patient import PatientProfile
from app.models.triage import PriorityLevel
from app.models.vitals import ExtractedObservation, ReadingContext

ACUTE_RED_FLAGS = {
    "chest_pain",
    "confusion",
    "unconscious",
    "shortness_of_breath",
}
MILD_SYMPTOMS = {
    "palpitations",
    "dizziness",
    "nausea",
    "sweating",
    "shakiness",
    "blurred_vision",
    "headache",
    "fatigue",
    "thirst",
}

CONFIDENCE_GATE = 0.80
HYPO_CRITICAL = 55.0
HYPER_CRITICAL = 400.0
HYPO_ALERT = 70.0


@dataclass
class TriageResult:
    priority: PriorityLevel
    reason: str
    circuit_breaker: bool
    emergency_english: str = ""


def _in_target(patient: PatientProfile, obs: ExtractedObservation) -> bool:
    value = obs.blood_glucose_mg_dl
    if value is None:
        return False
    if obs.reading_context == ReadingContext.FASTING:
        return patient.target_fasting_min <= value <= patient.target_fasting_max
    if obs.reading_context == ReadingContext.POST_PRANDIAL:
        return value <= patient.target_pp_max
    return patient.target_fasting_min <= value <= patient.target_pp_max


def triage_observation(patient: PatientProfile, obs: ExtractedObservation) -> TriageResult:
    value = obs.blood_glucose_mg_dl
    symptoms = set(obs.symptoms)
    acute = bool(symptoms & ACUTE_RED_FLAGS)
    mild = bool(symptoms & MILD_SYMPTOMS)

    # Life-threatening lows are evaluated before the confidence gate. Sending standard
    # Rule-of-15 guidance on a misread number is far safer than asking a hypoglycemic
    # patient to retake a photo.
    if value is not None and value < HYPO_CRITICAL:
        low_confidence = obs.confidence_score < CONFIDENCE_GATE
        caveat = (
            f" Extraction confidence {obs.confidence_score:.2f} is below the "
            f"{CONFIDENCE_GATE:.2f} gate — confirm the reading on the call."
            if low_confidence
            else ""
        )
        return TriageResult(
            priority=PriorityLevel.P0_CRITICAL,
            reason=f"Severe hypoglycemia {value:g} mg/dL (threshold < {HYPO_CRITICAL:g}).{caveat}",
            circuit_breaker=True,
            emergency_english=_rule_of_15(value),
        )

    if obs.device_error and value is None:
        return TriageResult(
            priority=PriorityLevel.P3_UNCLEAR,
            reason=f"Device error {obs.device_error}; no numeric glucose to triage.",
            circuit_breaker=False,
        )

    if obs.confidence_score < CONFIDENCE_GATE or value is None:
        return TriageResult(
            priority=PriorityLevel.P3_UNCLEAR,
            reason=(
                f"Extraction confidence {obs.confidence_score:.2f} "
                f"{'and missing glucose' if value is None else ''}. Clarification required."
            ),
            circuit_breaker=False,
        )

    if value > HYPER_CRITICAL and (acute or mild):
        return TriageResult(
            priority=PriorityLevel.P0_CRITICAL,
            reason=(
                f"Severe hyperglycemia {value:g} mg/dL with acute/distress symptoms "
                f"({', '.join(sorted(symptoms)) or 'distress'})."
            ),
            circuit_breaker=True,
            emergency_english=_hyper_emergency(value),
        )

    if acute:
        return TriageResult(
            priority=PriorityLevel.P0_CRITICAL,
            reason=f"Red-flag symptom(s) {sorted(symptoms & ACUTE_RED_FLAGS)} with glucose {value:g} mg/dL.",
            circuit_breaker=True,
            emergency_english=_red_flag_emergency(value, sorted(symptoms & ACUTE_RED_FLAGS)),
        )

    if value < HYPO_ALERT or not _in_target(patient, obs) or mild:
        bits = []
        if value < HYPO_ALERT:
            bits.append(f"glucose {value:g} below 70 mg/dL")
        if not _in_target(patient, obs):
            bits.append(
                f"{obs.reading_context.value} {value:g} outside personal target "
                f"(F {patient.target_fasting_min:g}–{patient.target_fasting_max:g}, "
                f"PP ≤{patient.target_pp_max:g})"
            )
        if mild:
            bits.append(f"symptoms: {', '.join(sorted(symptoms & MILD_SYMPTOMS))}")
        return TriageResult(
            priority=PriorityLevel.P1_ESCALATION,
            reason="; ".join(bits) + ".",
            circuit_breaker=False,
        )

    return TriageResult(
        priority=PriorityLevel.P2_ROUTINE,
        reason=f"{obs.reading_context.value} {value:g} mg/dL is within personal target. Logged to EMR.",
        circuit_breaker=False,
    )


def _rule_of_15(value: float) -> str:
    return (
        f"Warning: Your blood sugar is critically low ({value:g} mg/dL). "
        "Consume 15 grams of fast-acting sugar (half cup fruit juice or 3 sugar candies) immediately. "
        "Rest and recheck in 15 minutes. If you feel confused, faint, or cannot swallow, "
        "ask someone nearby to help and call emergency services (108)."
    )


def _hyper_emergency(value: float) -> str:
    return (
        f"Warning: Your blood sugar is critically high ({value:g} mg/dL) and you reported distress. "
        "Sit upright, sip water if you can, and do not take extra insulin on your own. "
        "A clinician is being alerted now. If you have chest pain, vomiting, or confusion, call 108."
    )


def _red_flag_emergency(value: float, flags: list[str]) -> str:
    pretty = ", ".join(flags).replace("_", " ")
    return (
        f"We received a danger symptom report ({pretty}) with glucose {value:g} mg/dL. "
        "This is not a diagnosis. If symptoms are severe, call 108 now. "
        "Stay with someone if possible. Your care team is being alerted immediately."
    )
