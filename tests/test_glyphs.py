"""The corridor trace and the colour rule behind it."""

import pytest

from app.models.patient import PatientProfile
from app.models.vitals import ReadingContext
from ui.design import ABOVE, BELOW, INSIDE, QUIET
from ui.glyphs import HYPO, corridor_trace, reading_tone


@pytest.fixture
def patient() -> PatientProfile:
    return PatientProfile(
        patient_id="P-T",
        full_name="Trace Test",
        phone_number="+910000000000",
        target_fasting_min=80,
        target_fasting_max=130,
        target_pp_max=180,
    )


def test_fasting_reading_is_judged_against_the_fasting_ceiling(patient):
    """Regression: 131 fasting is above target even though it is under the post-meal limit."""
    assert reading_tone(patient, 131, ReadingContext.FASTING) == ABOVE
    assert reading_tone(patient, 131, ReadingContext.POST_PRANDIAL) == INSIDE


def test_context_may_be_a_plain_string(patient):
    assert reading_tone(patient, 156, "FASTING") == ABOVE
    assert reading_tone(patient, 156, "POST_PRANDIAL") == INSIDE


def test_without_context_the_post_meal_ceiling_applies(patient):
    assert reading_tone(patient, 156) == INSIDE
    assert reading_tone(patient, 210) == ABOVE


@pytest.mark.parametrize("value", [40, 55, HYPO - 1, 79])
def test_low_readings_are_below(patient, value):
    assert reading_tone(patient, value, ReadingContext.FASTING) == BELOW


def test_missing_value_or_patient_is_quiet(patient):
    assert reading_tone(patient, None) == QUIET
    assert reading_tone(None, 120) == QUIET


def test_trace_is_accessible_svg(patient):
    svg = corridor_trace(patient, [(120, "FASTING"), (240, "POST_PRANDIAL")])
    assert svg.startswith("<svg")
    assert 'role="img"' in svg
    assert "aria-label" in svg
    assert "latest 240" in svg


def test_trace_without_readings_says_so(patient):
    svg = corridor_trace(patient, [])
    assert "no readings" in svg


def test_trace_marks_only_out_of_corridor_points(patient):
    inside_only = corridor_trace(patient, [(100, "FASTING"), (110, "FASTING"), (120, "FASTING")])
    # Two circles for the emphasised last point, none for the in-corridor ones.
    assert inside_only.count("<circle") == 2

    with_spike = corridor_trace(patient, [(100, "FASTING"), (260, "POST_PRANDIAL"), (120, "FASTING")])
    assert with_spike.count("<circle") == 3
    assert ABOVE in with_spike


def test_trace_caps_the_number_of_points(patient):
    from ui.glyphs import MAX_POINTS

    svg = corridor_trace(patient, [(120, "FASTING")] * 60)
    points = svg.split('points="')[1].split('"')[0].split(" ")
    assert len(points) == MAX_POINTS


def test_trace_clamps_extreme_values(patient):
    svg = corridor_trace(patient, [(20, "FASTING"), (600, "POST_PRANDIAL")], height=48)
    coords = svg.split('points="')[1].split('"')[0].split(" ")
    ys = [float(c.split(",")[1]) for c in coords]
    assert all(0 <= y <= 48 for y in ys)
