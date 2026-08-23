"""The panel: every patient as one scannable line, sorted by who needs a clinician."""

from __future__ import annotations

from typing import Optional

import streamlit as st

from app.analytics import (
    CONTROL_ACTION,
    CONTROL_GOOD,
    CONTROL_SILENT,
    CONTROL_WATCH,
    PatientSummary,
    summarize_panel,
)
from app.db.database import Repository
from ui.components.patient_record import render_patient_record
from ui.design import (
    ABOVE,
    BELOW,
    INSIDE,
    MUTED,
    STATUS_TONE,
    language_name,
)
from ui.glyphs import corridor_trace, reading_tone

PARAM = "patient"

SORTS = {
    "Who needs me": lambda s: (
        {CONTROL_ACTION: 0, CONTROL_SILENT: 1, CONTROL_WATCH: 2, CONTROL_GOOD: 3}[s.control_status],
        -s.open_alerts,
        -s.hypo_events_14d,
    ),
    "Name": lambda s: s.patient.full_name,
    "Least time in corridor": lambda s: (s.time_in_range if s.time_in_range is not None else -1),
    "Quietest": lambda s: -(s.days_quiet if s.days_quiet is not None else 999),
    "Oldest HbA1c": lambda s: -(s.hba1c_days if s.hba1c_days is not None else 0),
}

COLUMNS = ["Patient", "Recent readings against target", "Latest", "Logged", "In corridor", "Alerts"]


def render_roster(repo: Repository) -> None:
    selected_id = st.query_params.get(PARAM)
    if selected_id:
        patient = repo.get_patient(selected_id)
        if patient:
            st.markdown(
                '<a class="gs-back" href="?" target="_self">&larr; Back to the panel</a>',
                unsafe_allow_html=True,
            )
            render_patient_record(repo, patient)
            return
        st.query_params.clear()

    summaries = summarize_panel(repo)
    shown = _controls(summaries)
    if not shown:
        st.markdown(
            '<div class="gs-empty"><b>No patients match</b>'
            "Clear the search or widen the status filter to see the rest of the panel.</div>",
            unsafe_allow_html=True,
        )
        return

    head = "".join(f"<span>{c}</span>" for c in COLUMNS)
    rows = "".join(_row(s) for s in shown)
    st.markdown(
        f'<div class="gs-roster"><div class="gs-roster__head"><span></span>{head}</div>{rows}</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"{len(shown)} of {len(summaries)} patients · select a name to open the record")


def _controls(summaries: list[PatientSummary]) -> list[PatientSummary]:
    search_col, status_col, sort_col = st.columns([2.2, 1.7, 1.5])
    with search_col:
        query = st.text_input(
            "Search",
            placeholder="Search by name, patient ID or phone",
            label_visibility="collapsed",
        )
    with status_col:
        statuses = st.multiselect(
            "Status",
            [CONTROL_ACTION, CONTROL_SILENT, CONTROL_WATCH, CONTROL_GOOD],
            placeholder="Every status",
            label_visibility="collapsed",
        )
    with sort_col:
        sort_by = st.selectbox("Sort", list(SORTS), label_visibility="collapsed")

    result = summaries
    if query:
        needle = query.strip().lower()
        result = [
            s
            for s in result
            if needle in s.patient.full_name.lower()
            or needle in s.patient.patient_id.lower()
            or needle in s.patient.phone_number
        ]
    if statuses:
        result = [s for s in result if s.control_status in statuses]
    return sorted(result, key=SORTS[sort_by])


def _logged(days: Optional[int]) -> str:
    if days is None:
        return "never"
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    return f"{days} days ago"


def _row(s: PatientSummary) -> str:
    patient = s.patient
    tone = STATUS_TONE[s.control_status]
    therapy = "insulin" if patient.insulin_dependent else "tablets"
    meta = (
        f"<span class='gs-mono'>{patient.patient_id}</span> · {patient.age}{patient.sex} · "
        f"{patient.city} · {language_name(patient.preferred_language)} · {therapy}"
    )

    if s.last_value is None:
        value_block = (
            f"<span class='gs-row__mg' style='color:{MUTED}'>&mdash;</span>"
            "<span class='gs-row__unit'>no reading</span>"
        )
    else:
        value_tone = reading_tone(patient, s.last_value, s.last_context_key)
        value_block = (
            f"<span class='gs-row__mg' style='color:{value_tone}'>{s.last_value:.0f}</span>"
            f"<span class='gs-row__unit'>mg/dL · {(s.last_context or '').lower()}</span>"
        )

    if s.time_in_range is None:
        corridor = "<span class='gs-row__pct' style='color:#8a94a2'>&mdash;</span>"
    else:
        tir = s.time_in_range
        fill = INSIDE if tir >= 70 else ABOVE if tir >= 50 else BELOW
        corridor = (
            f"<span class='gs-row__pct'>{tir:.0f}<i>%</i></span>"
            f"<span class='gs-row__bar'><span style='width:{tir:.0f}%;background:{fill}'></span></span>"
        )

    if s.open_alerts:
        pip_tone = BELOW if s.highest_priority and s.highest_priority.value == "P0_CRITICAL" else ABOVE
        alerts = f"<span class='gs-pip' style='background:{pip_tone}'>{s.open_alerts}</span>"
    else:
        alerts = "<span class='gs-pip gs-pip--none'>&mdash;</span>"

    return (
        f'<a class="gs-row" href="?{PARAM}={patient.patient_id}" target="_self" '
        f'aria-label="Open the record for {patient.full_name}">'
        f'<span class="gs-row__flag" style="background:{tone}"></span>'
        f'<span class="gs-row__who">'
        f'<span class="gs-row__name">{patient.full_name}</span>'
        f'<span class="gs-row__meta">{meta}</span>'
        f"</span>"
        f'<span class="gs-row__trace">{corridor_trace(patient, s.recent_readings)}</span>'
        f'<span class="gs-row__value">{value_block}</span>'
        f'<span class="gs-row__when">{_logged(s.days_quiet)}</span>'
        f'<span class="gs-row__corridor">{corridor}</span>'
        f'<span class="gs-row__alerts">{alerts}</span>'
        f"</a>"
    )
