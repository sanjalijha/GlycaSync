"""Headless render tests for the console. Catches UI runtime errors without a browser."""

import os

import pytest
from streamlit.testing.v1 import AppTest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "ui", "app.py")


def open_console(section: str | None = None, **query) -> AppTest:
    app = AppTest.from_file(APP, default_timeout=90)
    for key, value in query.items():
        app.query_params[key] = value
    app.run()
    if section:
        nav = app.radio[0]
        label = next(o for o in nav.options if o.startswith(section))
        nav.set_value(label).run()
    return app


def html(app: AppTest) -> str:
    return " ".join(m.value for m in app.markdown)


@pytest.fixture(scope="module")
def panel() -> AppTest:
    return open_console()


def test_panel_renders_without_exception(panel):
    assert not panel.exception


def test_masthead_and_safety_note(panel):
    body = html(panel)
    assert "GlycaSync" in body
    assert "Diabetes Clinic" not in body
    assert "does not diagnose" in body
    assert "approved by a clinician" in body


def test_no_hackathon_copy(panel):
    body = html(panel).lower()
    for banned in ["health-a-thon", "healthathon", "judge", "hackathon", "langgraph pipeline"]:
        assert banned not in body


def test_every_patient_has_a_row(panel):
    body = html(panel)
    assert body.count('class="gs-row"') == 10


def test_rows_link_to_the_record(panel):
    for pid in ["P-1001", "P-1005", "P-1010"]:
        assert f"?patient={pid}" in html(panel)


def test_rows_carry_a_corridor_trace(panel):
    body = html(panel)
    assert body.count("<svg") >= 10
    assert "role=\"img\"" in body
    assert "aria-label" in body


def test_round_strip_counts_the_panel(panel):
    body = html(panel)
    for label in ["Needs action", "No recent data", "Watch", "In range", "Waiting on me"]:
        assert label in body


def test_readings_render_as_whole_numbers(panel):
    import re

    for value in re.findall(r'class=.gs-row__mg.[^>]*>([^<]+)<', html(panel)):
        assert "." not in value, value


def test_record_opens_from_a_query_parameter():
    app = open_console(patient="P-1001")
    assert not app.exception
    body = html(app)
    assert "Rajesh Kumar" in body
    assert "Their corridor" in body
    assert "Back to the panel" in body
    labels = [t.label for t in app.tabs]
    assert labels[:3] == ["Trend", "Care plan", "WhatsApp thread"]


def test_record_shows_the_glucose_trend_chart():
    app = open_console(patient="P-1001")
    assert not app.exception
    assert len(app.get("plotly_chart")) >= 2


def test_unknown_patient_falls_back_to_the_panel():
    app = open_console(patient="P-does-not-exist")
    assert not app.exception
    assert 'class="gs-row"' in html(app)


def test_alerts_queue_renders():
    app = open_console("Alerts")
    assert not app.exception
    assert app.expander, "expected at least one alert to review"


def test_intake_renders():
    app = open_console("Intake")
    assert not app.exception
    assert len(app.tabs) >= 3


def test_whatsapp_section_renders():
    app = open_console("WhatsApp")
    assert not app.exception
    body = html(app)
    assert "Not connected" in body or "Connected" in body
    assert "Account SID" not in body
    assert "Auth token" not in body
    assert "TWILIO_" not in body
