"""GlycaSync — the care team console."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from app.analytics import (
    CONTROL_ACTION,
    CONTROL_GOOD,
    CONTROL_SILENT,
    CONTROL_WATCH,
    panel_totals,
    summarize_panel,
)
from app.config import get_settings
from app.db.database import get_repo
from app.db.seed_data import ensure_seeded
from app.models.triage import ActionStatus, PriorityLevel
from app.simulator.mock_ingress import ensure_static_assets
from ui.components.alerts import render_alerts
from ui.components.channel import render_channel
from ui.components.intake import render_intake
from ui.components.roster import render_roster
from ui.design import CSS, INK, STATUS_NOTE, STATUS_TONE, STATUS_WASH

st.set_page_config(
    page_title="GlycaSync — Care Team",
    page_icon="◐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ensure_seeded()
ensure_static_assets()
settings = get_settings()
repo = get_repo()
st.markdown(CSS, unsafe_allow_html=True)

summaries = summarize_panel(repo)
totals = panel_totals(summaries)
open_tickets = [
    t for t in repo.list_tickets() if t.status in {ActionStatus.PENDING, ActionStatus.AUTO_DISPATCHED}
]
critical = [t for t in open_tickets if t.priority == PriorityLevel.P0_CRITICAL]

if settings.twilio_enabled:
    from app.integrations.webhook_server import ensure_webhook_running

    ensure_webhook_running()
    channel = "<b>WhatsApp</b> connected"
else:
    channel = "<b>WhatsApp</b> not connected"

_now = datetime.now()
now = _now.strftime(f"%a {_now.day} %b · %H:%M")
st.markdown(
    f"""
    <div class="gs-masthead">
      <div class="gs-masthead__brand">
        <span class="gs-mark">GlycaSync</span>
        <span class="gs-masthead__tag">AI-powered Diabetes Management</span>
      </div>
      <span class="gs-masthead__spacer"></span>
      <div class="gs-masthead__meta">
        <span class="gs-masthead__chip"><b>{len(summaries)}</b> on panel</span>
        <span class="gs-masthead__chip"><b>{len(open_tickets)}</b> waiting</span>
        <span class="gs-masthead__chip gs-masthead__chip--quiet">{now}</span>
        <span class="gs-channel">{channel}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if critical:
    who = []
    for ticket in critical:
        patient = repo.get_patient(ticket.patient_id)
        name = patient.full_name if patient else ticket.patient_id
        glucose = ticket.extracted_data.blood_glucose_mg_dl
        stamp = ticket.created_at.strftime("%H:%M")
        reading = f" at <span class='gs-mono'>{glucose:.0f} mg/dL</span>" if glucose else ""
        who.append(
            f"<a class='gs-critical__who' href='?patient={ticket.patient_id}' target='_self'>"
            f"{name}</a>{reading}, {stamp}"
        )
    st.markdown(
        f"""
        <div class="gs-critical">
          <span class="gs-critical__tag">Call now</span>
          <span class="gs-critical__body">{" &nbsp;·&nbsp; ".join(who)}
            &nbsp;—&nbsp; first-aid guidance already went out.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

round_cells = [
    (totals["needs_action"], CONTROL_ACTION),
    (totals["silent"], CONTROL_SILENT),
    (totals["watch"], CONTROL_WATCH),
    (totals["in_range"], CONTROL_GOOD),
]
cells = "".join(
    f'<div class="gs-round__cell" style="--wash:{STATUS_WASH[status]}">'
    f'<div class="gs-round__n" style="color:{STATUS_TONE[status] if count else "#c4cad3"}">{count}</div>'
    f'<div class="gs-round__label">{status}</div>'
    f'<div class="gs-round__note">{STATUS_NOTE[status]}</div>'
    f"</div>"
    for count, status in round_cells
)
cells += (
    f'<div class="gs-round__cell" style="--wash:#f2f4f7">'
    f'<div class="gs-round__n" style="color:{INK if open_tickets else "#c4cad3"}">{len(open_tickets)}</div>'
    f'<div class="gs-round__label">Waiting on me</div>'
    f'<div class="gs-round__note">Drafted replies to approve</div>'
    f"</div>"
)
st.markdown(
    f'<div class="gs-board">'
    f'<div class="gs-board__head"><span class="gs-legend">This round</span>'
    f'<span class="gs-board__hint">Glucose relative to each patient&rsquo;s corridor</span></div>'
    f'<div class="gs-round">{cells}</div></div>',
    unsafe_allow_html=True,
)

sections = ["Panel", f"Alerts · {len(open_tickets)}", "Intake", "WhatsApp"]
section = st.radio(
    "Section",
    sections,
    horizontal=True,
    label_visibility="collapsed",
    key="section",
)

if section is None or section.startswith("Panel"):
    render_roster(repo)
elif section.startswith("Alerts"):
    render_alerts(repo)
elif section.startswith("Intake"):
    render_intake(repo)
else:
    render_channel(repo)

st.markdown(
    '<div class="gs-legend" style="margin-top:34px;padding-top:14px;'
    'border-top:1px solid var(--line);line-height:1.7;">'
    "GlycaSync reads what patients send and routes it to you. It does not diagnose, "
    "prescribe, or change a dose.<br>Every message to a patient is approved by a clinician, "
    "except first-aid guidance during a critical low.</div>",
    unsafe_allow_html=True,
)
