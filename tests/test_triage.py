"""Clinical safety tests for the triage engine. These encode the guardrails."""

import pytest

from app.agents.triage import triage_observation
from app.models.patient import PatientProfile
from app.models.triage import PriorityLevel
from app.models.vitals import ExtractedObservation, ReadingContext


@pytest.fixture
def patient() -> PatientProfile:
    return PatientProfile(
        patient_id="P-TEST",
        full_name="Test Patient",
        phone_number="+910000000000",
        target_fasting_min=80,
        target_fasting_max=130,
        target_pp_max=180,
    )


def obs(**kwargs) -> ExtractedObservation:
    defaults = {
        "patient_id": "P-TEST",
        "confidence_score": 0.95,
        "reading_context": ReadingContext.FASTING,
    }
    defaults.update(kwargs)
    return ExtractedObservation(**defaults)


@pytest.mark.parametrize("value", [20, 40, 48, 54, 54.9])
def test_severe_hypoglycemia_is_p0_with_circuit_breaker(patient, value):
    result = triage_observation(patient, obs(blood_glucose_mg_dl=value))
    assert result.priority == PriorityLevel.P0_CRITICAL
    assert result.circuit_breaker is True
    assert "15 grams" in result.emergency_english
    assert "108" in result.emergency_english


def test_hypo_boundary_55_is_not_p0(patient):
    result = triage_observation(patient, obs(blood_glucose_mg_dl=55))
    assert result.priority == PriorityLevel.P1_ESCALATION
    assert result.circuit_breaker is False


def test_low_but_not_severe_is_p1(patient):
    result = triage_observation(patient, obs(blood_glucose_mg_dl=64))
    assert result.priority == PriorityLevel.P1_ESCALATION


def test_severe_hyper_with_symptoms_is_p0(patient):
    result = triage_observation(
        patient, obs(blood_glucose_mg_dl=430, symptoms=["nausea"], reading_context=ReadingContext.RANDOM)
    )
    assert result.priority == PriorityLevel.P0_CRITICAL
    assert result.circuit_breaker is True


def test_severe_hyper_without_symptoms_is_p1_not_p0(patient):
    result = triage_observation(patient, obs(blood_glucose_mg_dl=430))
    assert result.priority == PriorityLevel.P1_ESCALATION


@pytest.mark.parametrize("flag", ["chest_pain", "confusion", "unconscious", "shortness_of_breath"])
def test_red_flag_symptoms_are_p0_at_any_glucose(patient, flag):
    result = triage_observation(patient, obs(blood_glucose_mg_dl=110, symptoms=[flag]))
    assert result.priority == PriorityLevel.P0_CRITICAL
    assert result.circuit_breaker is True


def test_in_range_fasting_is_routine(patient):
    result = triage_observation(patient, obs(blood_glucose_mg_dl=110))
    assert result.priority == PriorityLevel.P2_ROUTINE
    assert result.circuit_breaker is False


def test_fasting_boundaries_are_inclusive(patient):
    assert triage_observation(patient, obs(blood_glucose_mg_dl=80)).priority == PriorityLevel.P2_ROUTINE
    assert triage_observation(patient, obs(blood_glucose_mg_dl=130)).priority == PriorityLevel.P2_ROUTINE
    assert triage_observation(patient, obs(blood_glucose_mg_dl=131)).priority == PriorityLevel.P1_ESCALATION


def test_post_prandial_uses_pp_target(patient):
    pp = triage_observation(
        patient, obs(blood_glucose_mg_dl=170, reading_context=ReadingContext.POST_PRANDIAL)
    )
    assert pp.priority == PriorityLevel.P2_ROUTINE
    fasting = triage_observation(
        patient, obs(blood_glucose_mg_dl=170, reading_context=ReadingContext.FASTING)
    )
    assert fasting.priority == PriorityLevel.P1_ESCALATION


def test_in_range_with_mild_symptoms_escalates(patient):
    result = triage_observation(patient, obs(blood_glucose_mg_dl=110, symptoms=["dizziness"]))
    assert result.priority == PriorityLevel.P1_ESCALATION


def test_low_confidence_is_unclear(patient):
    result = triage_observation(patient, obs(blood_glucose_mg_dl=110, confidence_score=0.62))
    assert result.priority == PriorityLevel.P3_UNCLEAR


def test_confidence_gate_boundary(patient):
    assert triage_observation(patient, obs(blood_glucose_mg_dl=110, confidence_score=0.80)).priority == (
        PriorityLevel.P2_ROUTINE
    )
    assert triage_observation(patient, obs(blood_glucose_mg_dl=110, confidence_score=0.79)).priority == (
        PriorityLevel.P3_UNCLEAR
    )


def test_device_error_without_value_is_unclear(patient):
    result = triage_observation(patient, obs(device_error="E-1", confidence_score=0.9))
    assert result.priority == PriorityLevel.P3_UNCLEAR
    assert result.circuit_breaker is False


def test_missing_glucose_is_unclear(patient):
    result = triage_observation(patient, obs(blood_glucose_mg_dl=None))
    assert result.priority == PriorityLevel.P3_UNCLEAR


def test_hypo_beats_low_confidence(patient):
    """A readable critical low must never be downgraded to a clarification prompt."""
    result = triage_observation(patient, obs(blood_glucose_mg_dl=42, confidence_score=0.55))
    assert result.priority == PriorityLevel.P0_CRITICAL


def test_personal_targets_are_respected(patient):
    lenient = patient.model_copy(update={"target_fasting_max": 160})
    result = triage_observation(lenient, obs(blood_glucose_mg_dl=150))
    assert result.priority == PriorityLevel.P2_ROUTINE
    assert triage_observation(patient, obs(blood_glucose_mg_dl=150)).priority == PriorityLevel.P1_ESCALATION


def test_no_emergency_text_contains_dosage_advice(patient):
    """Guardrail: the circuit breaker must never titrate medication."""
    result = triage_observation(patient, obs(blood_glucose_mg_dl=45))
    lowered = result.emergency_english.lower()
    for banned in ("increase your insulin", "take extra insulin", "double your dose", "units of insulin"):
        assert banned not in lowered
