"""The alert queue: what an agent flagged, what it drafted, and the clinician's call."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import streamlit as st

from app.agents.graph import dispatch_ticket
from app.db.database import Repository
from app.models.patient import PatientProfile
from app.models.triage import ActionStatus, PriorityLevel, TicketType, TriageTicket
from ui.design import (
    BELOW,
    MUTED,
    PRIORITY_LABEL,
    PRIORITY_TONE,
    PRIORITY_WASH,
    SLATE,
    language_name,
)
from ui.glyphs import reading_tone

QUEUES = {
    "Waiting on me": [ActionStatus.PENDING, ActionStatus.AUTO_DISPATCHED],
    "Sent": [ActionStatus.APPROVED],
    "Closed": [ActionStatus.RESOLVED, ActionStatus.REJECTED],
    "Everything": list(ActionStatus),
}

# Where the alert came from. The priority tag already says how urgent it is, so these
# never repeat it.
SOURCE = {
    TicketType.INGRESS: "Patient wrote in",
    TicketType.OUTREACH: "Record review",
    TicketType.EMERGENCY: "Patient wrote in",
}


def render_alerts(repo: Repository) -> None:
    patients = {p.patient_id: p for p in repo.list_patients()}

    queue_col, source_col, priority_col = st.columns([1.4, 1.4, 1.4])
    with queue_col:
        queue = st.selectbox("Queue", list(QUEUES), label_visibility="collapsed")
    with source_col:
        source = st.selectbox(
            "Source", ["Every source"] + [SOURCE[t] for t in TicketType], label_visibility="collapsed"
        )
    with priority_col:
        priority = st.selectbox(
            "Priority",
            ["Every priority"] + [PRIORITY_LABEL[p] for p in PriorityLevel],
            label_visibility="collapsed",
        )

    tickets = [t for t in repo.list_tickets() if t.status in QUEUES[queue]]
    if source != "Every source":
        tickets = [t for t in tickets if SOURCE[t.ticket_type] == source]
    if priority != "Every priority":
        tickets = [t for t in tickets if PRIORITY_LABEL[t.priority] == priority]

    routine = [
        t for t in tickets if t.ticket_type == TicketType.OUTREACH and t.status == ActionStatus.PENDING
    ]
    if routine:
        left, right = st.columns([4, 1])
        left.caption(
            f"{len(routine)} reminder{'s' if len(routine) > 1 else ''} from the record review "
            "are drafted and ready."
        )
        if right.button(f"Send all {len(routine)}", type="primary", use_container_width=True):
            for ticket in routine:
                dispatch_ticket(ticket.ticket_id, reviewer="Care Coordinator", repo=repo)
            st.rerun()

    if not tickets:
        st.markdown(
            '<div class="gs-empty"><b>Queue is clear</b>'
            "Nothing in this queue needs a clinician right now.</div>",
            unsafe_allow_html=True,
        )
        return

    for ticket in tickets:
        render_alert(repo, ticket, patients.get(ticket.patient_id))


def render_alert(
    repo: Repository,
    ticket: TriageTicket,
    patient: Optional[PatientProfile],
    *,
    compact: bool = False,
    key_prefix: str = "queue",
) -> None:
    tone = PRIORITY_TONE[ticket.priority]
    obs = ticket.extracted_data
    glucose = obs.blood_glucose_mg_dl

    if not compact:
        value_tone = reading_tone(patient, glucose, obs.reading_context)
        reading = f"{glucose:.0f}" if glucose is not None else "—"
        unit = (
            f"mg/dL · {obs.reading_context.value.replace('_', ' ').lower()} · read at {obs.confidence_score:.0%}"
            if glucose is not None
            else "no reading extracted"
        )
        name = patient.full_name if patient else ticket.patient_id
        where = f"{patient.city} · {language_name(patient.preferred_language)}" if patient else ""
        st.markdown(
            f"""
            <div class="gs-alert" style="border-left-color:{tone};background:{PRIORITY_WASH[ticket.priority]};">
              <div class="gs-alert__top">
                <div>
                  <div class="gs-alert__tag" style="color:{tone}">
                    {PRIORITY_LABEL[ticket.priority]} &nbsp;·&nbsp; {SOURCE[ticket.ticket_type]}
                  </div>
                  <div class="gs-alert__name">{name}</div>
                  <div class="gs-alert__meta gs-mono">{ticket.patient_id} · {where} ·
                    {ticket.created_at.strftime("%d %b, %H:%M")}</div>
                </div>
                <div>
                  <div class="gs-alert__read" style="color:{value_tone}">{reading}</div>
                  <div class="gs-alert__unit">{unit}</div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.expander(ticket.triage_reason, expanded=ticket.priority == PriorityLevel.P0_CRITICAL):
        evidence, action = st.columns([1, 1.15])
        with evidence:
            _evidence(ticket, patient)
        with action:
            _action(repo, ticket, patient, key_prefix)


def _evidence(ticket: TriageTicket, patient: Optional[PatientProfile]) -> None:
    obs = ticket.extracted_data
    st.markdown('<div class="gs-legend">What came in</div>', unsafe_allow_html=True)
    if obs.raw_transcript:
        st.markdown(f'<div class="gs-said">{obs.raw_transcript}</div>', unsafe_allow_html=True)
        if obs.translated_text and obs.translated_text != obs.raw_transcript:
            st.markdown(
                f'<div class="gs-said gs-said--translated">In English: {obs.translated_text}</div>',
                unsafe_allow_html=True,
            )
    elif ticket.ticket_type == TicketType.OUTREACH:
        st.markdown(
            f'<div class="gs-said" style="color:{MUTED};">The record review raised this. '
            "The patient has not written in.</div>",
            unsafe_allow_html=True,
        )
    if obs.image_url and Path(obs.image_url).exists():
        st.image(obs.image_url, caption="Photo the patient sent", width=250)

    st.markdown('<div class="gs-legend" style="margin-top:14px;">What we read</div>', unsafe_allow_html=True)
    facts = []
    if obs.blood_glucose_mg_dl is not None:
        facts.append(
            f"<b>{obs.blood_glucose_mg_dl:.0f} mg/dL</b> "
            f"{obs.reading_context.value.replace('_', ' ').lower()}"
        )
    if obs.symptoms:
        facts.append("Reported " + ", ".join(s.replace("_", " ") for s in obs.symptoms))
    if obs.device_error:
        facts.append(f"Meter showed <b>{obs.device_error}</b>")
    facts.append(f"Read with <b>{obs.confidence_score:.0%}</b> confidence")
    if patient:
        facts.append(
            f"Their corridor is <b>{patient.target_fasting_min:.0f}–{patient.target_fasting_max:.0f}</b> "
            f"fasting, <b>{patient.target_pp_max:.0f}</b> after a meal"
        )
    st.markdown(
        '<div class="gs-facts">' + "".join(f"<div>{f}</div>" for f in facts) + "</div>",
        unsafe_allow_html=True,
    )


def _action(
    repo: Repository,
    ticket: TriageTicket,
    patient: Optional[PatientProfile],
    key_prefix: str,
) -> None:
    waiting = ticket.status in {ActionStatus.PENDING, ActionStatus.AUTO_DISPATCHED}

    if ticket.priority == PriorityLevel.P0_CRITICAL and patient:
        st.markdown(
            f'<div class="gs-legend" style="color:{BELOW};">Call now</div>', unsafe_allow_html=True
        )
        a, b = st.columns(2)
        a.link_button(
            patient.full_name,
            f"tel:{patient.phone_number}",
            type="primary",
            use_container_width=True,
        )
        if patient.emergency_phone:
            b.link_button(
                patient.emergency_contact or "Emergency contact",
                f"tel:{patient.emergency_phone}",
                use_container_width=True,
            )

    if ticket.status == ActionStatus.AUTO_DISPATCHED and ticket.dispatched_message:
        st.markdown(
            '<div class="gs-legend" style="margin-top:12px;">Already sent to the patient</div>',
            unsafe_allow_html=True,
        )
        st.markdown(f'<div class="gs-out">{ticket.dispatched_message}</div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="gs-legend" style="margin-top:12px;">Your reply</div>', unsafe_allow_html=True
    )
    edited = st.text_area(
        "Reply",
        value=ticket.drafted_response,
        key=f"{key_prefix}-draft-{ticket.ticket_id}",
        height=150,
        label_visibility="collapsed",
        disabled=not waiting,
    )
    if ticket.drafted_response_localized and patient:
        with st.expander(f"How it reads in {language_name(patient.preferred_language)}"):
            st.write(ticket.drafted_response_localized)

    if not waiting:
        st.markdown(
            f'<div class="gs-legend" style="margin-top:10px;color:{SLATE};">'
            f"{ticket.status.value.title()} by {ticket.reviewed_by or 'the care team'}</div>",
            unsafe_allow_html=True,
        )
        return

    # During a critical low the call is the action; the reply is a follow-up, so it
    # does not compete for emphasis.
    reply_weight = "secondary" if ticket.priority == PriorityLevel.P0_CRITICAL else "primary"

    send, close, drop = st.columns([1.4, 1, 1])
    if send.button(
        "Send reply",
        key=f"{key_prefix}-send-{ticket.ticket_id}",
        type=reply_weight,
        use_container_width=True,
    ):
        dispatch_ticket(ticket.ticket_id, edited_english=edited, repo=repo)
        st.rerun()
    if close.button("Close", key=f"{key_prefix}-close-{ticket.ticket_id}", use_container_width=True):
        repo.update_ticket(ticket.ticket_id, status=ActionStatus.RESOLVED, reviewed_by="Care Coordinator")
        st.rerun()
    if drop.button("Dismiss", key=f"{key_prefix}-drop-{ticket.ticket_id}", use_container_width=True):
        repo.update_ticket(ticket.ticket_id, status=ActionStatus.REJECTED, reviewed_by="Care Coordinator")
        st.rerun()
