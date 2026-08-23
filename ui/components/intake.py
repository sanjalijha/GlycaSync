"""Log a reading that arrived off-channel, run the record review, read the send log."""

from __future__ import annotations

import streamlit as st

from app.agents.auditor import audit_emr
from app.agents.graph import run_ingress_graph
from app.config import get_settings
from app.db.database import Repository
from app.models.triage import PriorityLevel
from ui.design import INK, MUTED, PRIORITY_LABEL, PRIORITY_TONE, SLATE, language_name
from ui.glyphs import reading_tone

EXAMPLES = {
    "Start from blank": "",
    "High after a meal, with palpitations": "Khane ke baad sugar 245 hai, thodi ghabrahat ho rahi hai",
    "Severe low, feeling shaky": "Sugar 48, feeling very shaky",
    "Fasting reading, in range": "Fasting 105 this morning, feeling fine",
    "Meter showing an error": "machine pe E-1 error aa raha hai",
}


def render_intake(repo: Repository) -> None:
    log_tab, review_tab, sent_tab = st.tabs(["Log a reading", "Record review", "Sent messages"])
    with log_tab:
        _log(repo)
    with review_tab:
        _review(repo)
    with sent_tab:
        _sent(repo)


def _log(repo: Repository) -> None:
    st.caption(
        "For readings a patient gave you on a call or at the desk. It runs through the same "
        "reading and triage steps as a WhatsApp message."
    )
    patients = repo.list_patients()
    if not patients:
        st.markdown(
            '<div class="gs-empty"><b>No patients yet</b>Add a patient to log a reading.</div>',
            unsafe_allow_html=True,
        )
        return

    labels = {f"{p.full_name} · {p.patient_id}": p for p in patients}
    who, example = st.columns([1.5, 1])
    with who:
        patient = labels[st.selectbox("Patient", list(labels))]
    with example:
        chosen = st.selectbox("Example to start from", list(EXAMPLES))

    st.caption(
        f"{patient.full_name} speaks {language_name(patient.preferred_language)}. "
        f"Corridor {patient.target_fasting_min:.0f}–{patient.target_fasting_max:.0f} fasting, "
        f"under {patient.target_pp_max:.0f} after a meal."
    )
    text = st.text_area(
        "What the patient said",
        value=EXAMPLES[chosen],
        placeholder="Their reading and anything they mentioned, in English or their own language",
        height=100,
    )
    photo_col, send_col = st.columns([1, 1])
    with photo_col:
        photo = st.number_input(
            "Attach a meter photo showing",
            min_value=0,
            max_value=600,
            value=0,
            help="Builds a glucometer image so the photo-reading step runs too. Leave at 0 to skip.",
        )
    with send_col:
        st.write("")
        st.write("")
        submitted = st.button("Run it through triage", type="primary", use_container_width=True)

    if submitted:
        if not text.strip() and not photo:
            st.warning("Add what the patient said, or attach a meter photo.")
            return
        image_url = None
        if photo:
            from app.simulator.mock_ingress import render_glucometer

            path = get_settings().static_dir / f"glucometer_{int(photo):03d}.png"
            render_glucometer(path, int(photo))
            image_url = str(path)
        st.session_state["last_intake"] = run_ingress_graph(
            phone_number=patient.phone_number,
            patient_id=patient.patient_id,
            raw_text=text,
            image_url=image_url,
        )
        st.rerun()

    result = st.session_state.get("last_intake")
    if result:
        _outcome(repo, result)


def _outcome(repo: Repository, result: dict) -> None:
    st.divider()
    if result.get("error"):
        st.error(result["error"])
        return

    priority = PriorityLevel(result["priority"])
    tone = PRIORITY_TONE[priority]
    extracted = result.get("extracted") or {}
    glucose = extracted.get("blood_glucose_mg_dl")
    patient = repo.get_patient(result.get("patient_id") or "")
    value_tone = reading_tone(patient, glucose, extracted.get("reading_context"))

    outcome = (
        "Sent to the patient"
        if result.get("auto_dispatched")
        else "Filed to the record"
        if result.get("skipped_ticket")
        else "Waiting for your approval"
    )
    symptoms = ", ".join(extracted.get("symptoms") or []) or "none mentioned"
    st.markdown(
        f"""
        <div class="gs-vitals">
          <div class="gs-vitals__cell">
            <div class="gs-legend">Reading</div>
            <div class="gs-vitals__v" style="color:{value_tone}">
              {f"{glucose:.0f}" if glucose else "—"}</div>
            <div class="gs-vitals__n">{"mg/dL" if glucose else "nothing extracted"}</div>
          </div>
          <div class="gs-vitals__cell">
            <div class="gs-legend">Symptoms</div>
            <div class="gs-vitals__v" style="font-size:15px;color:{INK};">{symptoms}</div>
            <div class="gs-vitals__n">as reported</div>
          </div>
          <div class="gs-vitals__cell">
            <div class="gs-legend">Triage</div>
            <div class="gs-vitals__v" style="font-size:17px;color:{tone};">{PRIORITY_LABEL[priority]}</div>
            <div class="gs-vitals__n">{outcome}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="gs-legend" style="color:{SLATE};">Why</div>'
        f'<div class="gs-facts">{result.get("triage_reason", "")}</div>',
        unsafe_allow_html=True,
    )
    if result.get("drafted_response"):
        st.markdown(
            '<div class="gs-legend" style="margin-top:12px;">Draft reply</div>', unsafe_allow_html=True
        )
        st.markdown(f'<div class="gs-out">{result["drafted_response"]}</div>', unsafe_allow_html=True)
    if result.get("ticket_id"):
        st.caption(f"Open it under Alerts to approve and send · {result['ticket_id']}")


def _review(repo: Repository) -> None:
    st.caption(
        "Checks every record for HbA1c tests past 90 days, follow-ups that were missed, and "
        "patients on insulin who have gone quiet. Anything it finds is drafted for your approval."
    )
    if st.button("Run the review", type="primary"):
        created = audit_emr(repo)
        if not created:
            st.markdown(
                '<div class="gs-empty"><b>Everyone is up to date</b>'
                "No overdue tests, missed follow-ups, or quiet patients.</div>",
                unsafe_allow_html=True,
            )
            return
        st.success(f"Drafted {len(created)} reminder{'s' if len(created) > 1 else ''} for approval.")
        rows = []
        for ticket in created:
            patient = repo.get_patient(ticket.patient_id)
            rows.append(
                f'<div style="padding:9px 0;border-bottom:1px solid #eef1f5;font-size:13.5px;">'
                f'<span style="font-weight:600;color:{INK};">'
                f"{patient.full_name if patient else ticket.patient_id}</span>"
                f'<span style="color:{MUTED};"> — {ticket.triage_reason}</span></div>'
            )
        st.markdown("".join(rows), unsafe_allow_html=True)


def _sent(repo: Repository) -> None:
    settings = get_settings()
    if settings.twilio_enabled:
        st.caption("WhatsApp is connected. Everything below was delivered.")
    else:
        st.caption(
            "WhatsApp is not connected, so approved replies are recorded here instead of being "
            "delivered. Add Twilio credentials to .env to start sending."
        )

    messages = repo.recent_messages(limit=25, direction="OUT")
    if not messages:
        st.markdown(
            '<div class="gs-empty"><b>Nothing sent yet</b>'
            "Approved replies from the alert queue will show up here.</div>",
            unsafe_allow_html=True,
        )
        return
    blocks = []
    for msg in messages:
        patient = repo.get_patient(msg["patient_id"]) if msg["patient_id"] else None
        name = patient.full_name if patient else msg["phone_number"] or "Unknown number"
        stamp = (msg["created_at"] or "")[:16].replace("T", " ")
        blocks.append(
            f'<div class="gs-stamp">{name} · {msg["phone_number"]} · {stamp}</div>'
            f'<div class="gs-out">{msg["content"]}</div>'
        )
    st.markdown("".join(blocks), unsafe_allow_html=True)
