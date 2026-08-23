"""WhatsApp operations: attach a live number, send a test. Credentials stay in `.env`."""

from __future__ import annotations

import streamlit as st

from app.config import get_settings
from app.db.database import Repository
from app.integrations.twilio_wa import WhatsAppGateway, normalize_e164
from app.integrations.webhook_server import ensure_webhook_running, listener_status
from ui.design import INK, SLATE

LIVE_NUMBER = "+919821487690"
TEST_BODY = (
    "GlycaSync is connected. Reply with a glucose reading any time — a photo of "
    "the meter, a voice note, or the number in a text."
)


def render_channel(repo: Repository) -> None:
    settings = get_settings()
    listener = ensure_webhook_running() if settings.twilio_enabled else listener_status()
    _status(settings, listener)

    inbox_tab, attach_tab, test_tab = st.tabs(["Received", "Attach a number", "Send a test"])
    with inbox_tab:
        _received(repo)
    with attach_tab:
        _attach_number(repo)
    with test_tab:
        _test_send(repo, settings)


def _received(repo: Repository) -> None:
    st.caption("Every inbound WhatsApp from Twilio, including numbers not yet on a chart.")
    messages = repo.recent_messages(limit=40, direction="IN")
    if not messages:
        st.markdown(
            '<div class="gs-empty"><b>Nothing received yet</b>'
            "When a patient writes in, the message lands here and on their thread.</div>",
            unsafe_allow_html=True,
        )
        return
    blocks = []
    for msg in messages:
        patient = repo.get_patient(msg["patient_id"]) if msg["patient_id"] else None
        who = patient.full_name if patient else "Unknown number"
        stamp = (msg["created_at"] or "")[:16].replace("T", " ")
        blocks.append(
            f'<div class="gs-stamp">{who} · {msg["phone_number"]} · {stamp}</div>'
            f'<div class="gs-in">{msg["content"]}</div>'
        )
    st.markdown("".join(blocks), unsafe_allow_html=True)


def _status(settings, listener: dict) -> None:
    if settings.twilio_enabled:
        st.markdown(
            f'<div class="gs-legend" style="margin-bottom:8px;color:{INK};">Connected</div>'
            '<div class="gs-facts">Approved replies and critical-low first aid '
            "are delivered on WhatsApp.</div>",
            unsafe_allow_html=True,
        )
        if listener["running"]:
            st.caption("Inbound messages are being accepted on this machine.")
        elif listener.get("error"):
            st.caption("The inbound listener could not start. Restart the console and try again.")
        if not listener["public"]:
            st.caption(
                "Twilio cannot reach this machine from the internet yet. "
                "Expose port 8000 with a tunnel and set PUBLIC_BASE_URL in `.env` "
                "to that https address."
            )
        return

    st.markdown(
        f'<div class="gs-legend" style="margin-bottom:8px;color:{SLATE};">Not connected</div>'
        '<div class="gs-facts">Approved replies are recorded here, not sent. '
        "Put the Twilio values in `.env` and restart the console.</div>",
        unsafe_allow_html=True,
    )


def _attach_number(repo: Repository) -> None:
    st.caption(
        "Inbound messages are matched to a chart by the last 10 digits. Attach the "
        "phone a patient will write from — otherwise the message is recorded and ignored."
    )
    patients = repo.list_patients()
    if not patients:
        st.markdown(
            '<div class="gs-empty"><b>No patients yet</b>Seed the panel first.</div>',
            unsafe_allow_html=True,
        )
        return

    labels = {f"{p.full_name} · {p.patient_id}": p for p in patients}
    chosen = st.selectbox("Patient", list(labels))
    patient = labels[chosen]
    phone = st.text_input("Patient WhatsApp number", value=LIVE_NUMBER)
    if st.button("Attach this number", type="primary"):
        try:
            updated = repo.set_patient_phone(patient.patient_id, phone)
        except ValueError as exc:
            st.error(str(exc))
            return
        st.success(
            f"{updated.full_name} will now receive messages sent from that number."
        )


def _test_send(repo: Repository, settings) -> None:
    if not settings.twilio_enabled:
        st.markdown(
            '<div class="gs-empty"><b>WhatsApp is not connected</b>'
            "Add the Twilio values to `.env` and restart.</div>",
            unsafe_allow_html=True,
        )
        return

    attached = next(
        (p for p in repo.list_patients() if normalize_e164(p.phone_number) == LIVE_NUMBER),
        None,
    )
    to = st.text_input("Send to", value=LIVE_NUMBER)
    body = st.text_area("Message", value=TEST_BODY, height=90)
    if st.button("Send test message", type="primary"):
        number = normalize_e164(to)
        if not number:
            st.error("Enter a destination number.")
            return
        patient = repo.get_patient_by_phone(number)
        record = WhatsAppGateway(repo).send_text(
            number,
            body,
            patient_id=patient.patient_id if patient else None,
        )
        if record["live"]:
            who = patient.full_name if patient else "that number"
            st.success(f"Delivered to {who}.")
        else:
            st.error(record.get("error") or "Twilio did not accept the message.")
    if attached:
        st.caption(f"Attached to {attached.full_name}.")
