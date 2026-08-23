"""Outbound drafts must name the clinical situation, not book an appointment."""

from app.agents.synthesizer import (
    outreach_consult_draft,
    outreach_dropoff_draft,
    outreach_hba1c_draft,
    synthesize_reply,
)
from app.agents.triage import triage_observation
from app.models.patient import PatientProfile
from app.models.triage import PriorityLevel
from app.models.vitals import ExtractedObservation, ReadingContext

BOOKING = ("reply yes", "book a", "slot", "home collection", "tele-consult")


def patient(**kwargs) -> PatientProfile:
    defaults = dict(
        patient_id="P-S",
        full_name="Rajesh Kumar",
        phone_number="+919811000001",
        insulin_dependent=True,
        last_hba1c_value=8.4,
    )
    defaults.update(kwargs)
    return PatientProfile(**defaults)


def observation(**kwargs) -> ExtractedObservation:
    kwargs.setdefault("patient_id", "P-S")
    return ExtractedObservation(**kwargs)


def draft(obs: ExtractedObservation, person: PatientProfile | None = None) -> str:
    who = person or patient()
    triage = triage_observation(who, obs)
    english, _ = synthesize_reply(who, obs, triage)
    return english.lower()


def test_high_after_meal_names_the_reading_and_forbids_extra_insulin():
    text = draft(
        observation(
            blood_glucose_mg_dl=245,
            reading_context=ReadingContext.POST_PRANDIAL,
            symptoms=["palpitations"],
            confidence_score=0.94,
        )
    )
    assert "245" in text
    assert "after a meal" in text
    assert "palpitations" in text
    assert "insulin" in text
    assert all(phrase not in text for phrase in BOOKING)


def test_high_fasting_asks_for_the_next_post_meal_reading():
    text = draft(
        observation(
            blood_glucose_mg_dl=168,
            reading_context=ReadingContext.FASTING,
            confidence_score=0.95,
        )
    )
    assert "168" in text
    assert "fasting" in text
    assert "after that meal" in text or "breakfast" in text


def test_mild_low_gives_the_15_gram_rule_not_a_clinic_visit():
    text = draft(
        observation(
            blood_glucose_mg_dl=62,
            reading_context=ReadingContext.RANDOM,
            symptoms=["shakiness"],
            confidence_score=0.96,
        )
    )
    assert "62" in text
    assert "15" in text
    assert "108" in text
    assert all(phrase not in text for phrase in BOOKING)


def test_device_error_asks_for_a_new_strip_and_a_number():
    text = draft(observation(device_error="E-1", confidence_score=0.3))
    assert "e-1" in text
    assert "strip" in text
    assert "number" in text or "photo" in text


def test_in_range_confirms_the_corridor():
    text = draft(
        observation(
            blood_glucose_mg_dl=105,
            reading_context=ReadingContext.FASTING,
            confidence_score=0.95,
        )
    )
    assert "105" in text
    assert "inside" in text or "corridor" in text or "logged" in text


def test_hba1c_outreach_asks_for_the_report_not_a_booking():
    english, _ = outreach_hba1c_draft(patient(), 110)
    text = english.lower()
    assert "8.4" in text
    assert "110" in text
    assert "report" in text
    assert all(phrase not in text for phrase in BOOKING)


def test_insulin_dropoff_asks_for_todays_fasting_number():
    english, _ = outreach_dropoff_draft(patient(), 6)
    text = english.lower()
    assert "6 days" in text
    assert "insulin" in text
    assert "fasting" in text
    assert all(phrase not in text for phrase in BOOKING)


def test_consult_outreach_asks_for_readings_not_a_slot():
    english, _ = outreach_consult_draft(patient(), 120)
    text = english.lower()
    assert "120" in text
    assert "fasting" in text
    assert all(phrase not in text for phrase in BOOKING)


def test_p0_keeps_the_emergency_script():
    obs = observation(
        blood_glucose_mg_dl=46,
        reading_context=ReadingContext.FASTING,
        symptoms=["shakiness"],
        confidence_score=0.96,
    )
    who = patient()
    triage = triage_observation(who, obs)
    assert triage.priority == PriorityLevel.P0_CRITICAL
    english, _ = synthesize_reply(who, obs, triage)
    assert "46" in english
    assert "15 grams" in english.lower() or "15 g" in english.lower()
