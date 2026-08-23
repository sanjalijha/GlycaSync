import pytest

from app.agents.extractor import extract_observation
from app.models.patient import PatientProfile
from app.models.vitals import ReadingContext


@pytest.fixture
def patient() -> PatientProfile:
    return PatientProfile(patient_id="P-TEST", full_name="Test Patient", phone_number="+910000000000")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("My sugar is 245 mg/dL", 245),
        ("sugar 118", 118),
        ("fasting 96", 96),
        ("blood glucose: 302", 302),
        ("Mera sugar 162 hai", 162),
        ("reading was 88 mgdl", 88),
    ],
)
def test_parses_glucose_from_text(patient, text, expected):
    result = extract_observation(patient, text=text)
    assert result.blood_glucose_mg_dl == expected


def test_hindi_hai_is_not_a_hi_device_error(patient):
    """Regression: 'hai' in transliterated Hindi must not read as the HI device code."""
    result = extract_observation(patient, text="Mera sugar 162 hai, thoda chakkar aa raha hai")
    assert result.device_error is None
    assert result.blood_glucose_mg_dl == 162
    assert "dizziness" in result.symptoms


@pytest.mark.parametrize(
    "text,code",
    [
        ("machine shows E-1", "E-1"),
        ("meter reads E1 error", "E-1"),
        ("display says HI", "HI"),
        ("display says LO", "LO"),
        ("low battery warning", "LOW_BATTERY"),
    ],
)
def test_detects_device_errors(patient, text, code):
    assert extract_observation(patient, text=text).device_error == code


@pytest.mark.parametrize(
    "text,context",
    [
        ("fasting 110", ReadingContext.FASTING),
        ("subah khali pet 110", ReadingContext.FASTING),
        ("khane ke baad 210", ReadingContext.POST_PRANDIAL),
        ("post prandial 210", ReadingContext.POST_PRANDIAL),
        ("bedtime 140", ReadingContext.BEDTIME),
        ("sugar 140", ReadingContext.RANDOM),
    ],
)
def test_detects_reading_context(patient, text, context):
    assert extract_observation(patient, text=text).reading_context == context


@pytest.mark.parametrize(
    "text,symptom",
    [
        ("thodi ghabrahat ho rahi hai", "palpitations"),
        ("chakkar aa raha hai", "dizziness"),
        ("feeling very shaky", "shakiness"),
        ("bahut pasina aa raha hai", "sweating"),
        ("seene mein dard", "chest_pain"),
        ("I feel confused", "confusion"),
        ("ulti jaisa lag raha hai", "nausea"),
    ],
)
def test_detects_indic_and_english_symptoms(patient, text, symptom):
    assert symptom in extract_observation(patient, text=text).symptoms


def test_glucose_from_image_filename(patient):
    result = extract_observation(
        patient, text="", image_url="/tmp/glucometer_245.png", modality="image"
    )
    assert result.blood_glucose_mg_dl == 245


def test_error_image_yields_low_confidence(patient):
    result = extract_observation(
        patient, text="kuch error aa raha hai", image_url="/tmp/glucometer_error.png", modality="image"
    )
    assert result.blood_glucose_mg_dl is None
    assert result.confidence_score < 0.80


def test_empty_message_has_floor_confidence(patient):
    result = extract_observation(patient, text="")
    assert result.confidence_score < 0.5
    assert result.blood_glucose_mg_dl is None


def test_implausible_values_rejected(patient):
    assert extract_observation(patient, text="sugar 5").blood_glucose_mg_dl is None
    assert extract_observation(patient, text="sugar 9999").blood_glucose_mg_dl is None


def test_confidence_never_out_of_bounds(patient):
    for text in ["", "sugar 110", "E-1 error", "245 mg/dL with chakkar"]:
        score = extract_observation(patient, text=text).confidence_score
        assert 0.0 <= score <= 1.0
