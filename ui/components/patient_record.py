"""One patient in full: their corridor, their trend, their plan, their thread."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.analytics import PatientSummary, in_target, summarize_patient
from app.db.database import Repository
from app.models.patient import PatientProfile
from app.models.triage import ActionStatus
from app.models.vitals import ReadingContext
from ui.design import (
    ABOVE,
    BELOW,
    GRAPHITE,
    HAIRLINE,
    INK,
    INSIDE,
    LINE,
    MUTED,
    PRIORITY_TONE,
    PRIORITY_LABEL,
    SLATE,
    STATUS_TONE,
    language_name,
)
from ui.glyphs import HYPO, reading_tone

MARKER = {
    ReadingContext.FASTING.value: ("Fasting", "#2b5f78"),
    ReadingContext.POST_PRANDIAL.value: ("After a meal", "#7a4f9e"),
    ReadingContext.RANDOM.value: ("Random", "#4a5568"),
    ReadingContext.BEDTIME.value: ("Bedtime", "#9a6a2c"),
}

PLOT_FONT = dict(family="IBM Plex Sans, sans-serif", size=11, color=SLATE)


def render_patient_record(repo: Repository, patient: PatientProfile, *, window_days: int = 30) -> None:
    summary = summarize_patient(repo, patient, window_days=window_days)
    _header(patient, summary)
    _vitals(patient, summary)

    trend, plan, thread, alerts = st.tabs(
        ["Trend", "Care plan", "WhatsApp thread", f"Alerts · {summary.open_alerts}"]
    )
    with trend:
        _trend(repo, patient, window_days)
    with plan:
        _plan(repo, patient)
    with thread:
        _thread(repo, patient)
    with alerts:
        _alerts(repo, patient)


def _header(patient: PatientProfile, summary: PatientSummary) -> None:
    tone = STATUS_TONE[summary.control_status]
    therapy = "Insulin" if patient.insulin_dependent else "Oral agents"
    meds = " · ".join(patient.medications) if patient.medications else "No medicines recorded"
    note = (
        f'<div class="gs-rx"><span class="gs-legend">Note</span> &nbsp;{patient.notes}</div>'
        if patient.notes
        else ""
    )
    st.markdown(
        f"""
        <div class="gs-record" style="border-left:3px solid {tone};">
          <div class="gs-record__top">
            <div>
              <div class="gs-record__name">{patient.full_name}</div>
              <div class="gs-record__meta">
                {patient.age} years · {patient.sex} · {patient.diabetes_type} · {therapy} ·
                {patient.city} · speaks {language_name(patient.preferred_language)}
              </div>
              <div class="gs-record__ids">{patient.patient_id} · ABHA {patient.abha_id or "—"} · {patient.phone_number}</div>
            </div>
            <div class="gs-corridor">
              <div class="gs-legend">Their corridor</div>
              <div class="gs-corridor__v">
                {patient.target_fasting_min:.0f}–{patient.target_fasting_max:.0f} fasting
              </div>
              <div class="gs-corridor__v">&le; {patient.target_pp_max:.0f} after a meal</div>
              <div class="gs-legend" style="color:{tone};margin-top:8px;">
                {summary.control_status}
              </div>
            </div>
          </div>
          <div class="gs-rx"><span class="gs-legend">On</span> &nbsp;{meds}</div>
          {note}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _vitals(patient: PatientProfile, summary: PatientSummary) -> None:
    tir = summary.time_in_range
    tir_tone = INK if tir is None else INSIDE if tir >= 70 else ABOVE if tir >= 50 else BELOW
    quiet = summary.days_quiet
    when = "today" if quiet == 0 else f"{quiet} days ago" if quiet is not None else "never"

    hba1c_tone = BELOW if (summary.hba1c_days or 0) > 90 else INK
    hba1c_note = (
        f"{summary.hba1c_days} days ago" if summary.hba1c_days is not None else "never recorded"
    )
    if (summary.hba1c_days or 0) > 90:
        hba1c_note += " · overdue"

    cells = [
        (
            "In corridor",
            f"{tir:.0f}%" if tir is not None else "—",
            f"{summary.readings_14d} readings · 14 days",
            tir_tone,
        ),
        (
            "Latest",
            f"{summary.last_value:.0f}" if summary.last_value is not None else "—",
            f"{(summary.last_context or 'no reading').lower()} · {when}",
            reading_tone(patient, summary.last_value, summary.last_context_key),
        ),
        ("Average", f"{summary.mean_14d or '—'}", "mg/dL over 14 days", INK),
        (
            "Lows",
            str(summary.hypo_events_14d),
            f"under {HYPO:.0f} mg/dL · 14 days",
            BELOW if summary.hypo_events_14d else INK,
        ),
        ("HbA1c", f"{summary.hba1c:g}%" if summary.hba1c else "—", hba1c_note, hba1c_tone),
    ]
    cells_html = "".join(
        f'<div class="gs-vitals__cell"><div class="gs-legend">{label}</div>'
        f'<div class="gs-vitals__v" style="color:{tone}">{value}</div>'
        f'<div class="gs-vitals__n">{note}</div></div>'
        for label, value, note, tone in cells
    )
    st.markdown(f'<div class="gs-vitals">{cells_html}</div>', unsafe_allow_html=True)


def _trend(repo: Repository, patient: PatientProfile, window_days: int) -> None:
    vitals = [v for v in repo.list_vitals(patient.patient_id) if v.blood_glucose_mg_dl is not None]
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows = []
    for v in vitals:
        ts = v.timestamp if v.timestamp.tzinfo else v.timestamp.replace(tzinfo=timezone.utc)
        if ts < cutoff:
            continue
        rows.append(
            {
                "time": ts,
                "glucose": v.blood_glucose_mg_dl,
                "context": v.reading_context.value,
                "label": MARKER[v.reading_context.value][0],
                "symptoms": ", ".join(s.replace("_", " ") for s in v.symptoms) or "none reported",
                "in_range": in_target(patient, v),
            }
        )
    if not rows:
        st.markdown(
            f'<div class="gs-empty"><b>Nothing logged in {window_days} days</b>'
            "Send a check-in from the Intake tab to start the record.</div>",
            unsafe_allow_html=True,
        )
        return

    df = pd.DataFrame(rows)
    fig = go.Figure()
    fig.add_hrect(
        y0=patient.target_fasting_min,
        y1=patient.target_pp_max,
        fillcolor=INSIDE,
        opacity=0.1,
        line_width=0,
        layer="below",
    )
    fig.add_hline(y=HYPO, line=dict(color=BELOW, width=1, dash="dot"))
    fig.add_annotation(
        x=1, y=HYPO, xref="paper", text=f"{HYPO:.0f} hypo", showarrow=False,
        font=dict(family="IBM Plex Mono, monospace", size=10, color=BELOW),
        yshift=-10, xanchor="right",
    )
    fig.add_annotation(
        x=0, y=patient.target_pp_max, xref="paper", text=f"corridor {patient.target_fasting_min:.0f}–{patient.target_pp_max:.0f}",
        showarrow=False, font=dict(family="IBM Plex Mono, monospace", size=10, color=INSIDE),
        yshift=10, xanchor="left",
    )
    fig.add_trace(
        go.Scatter(
            x=df["time"], y=df["glucose"], mode="lines",
            line=dict(color=INK, width=1.2, shape="linear"), opacity=0.28,
            hoverinfo="skip", showlegend=False,
        )
    )
    for context, group in df.groupby("context"):
        label, colour = MARKER[context]
        fig.add_trace(
            go.Scatter(
                x=group["time"], y=group["glucose"], mode="markers", name=label,
                marker=dict(size=8, color=colour, line=dict(width=1.2, color="#fff")),
                customdata=group[["label", "symptoms"]],
                hovertemplate=(
                    "<b>%{y:.0f} mg/dL</b><br>%{customdata[0]}<br>"
                    "%{x|%d %b, %H:%M}<br>Symptoms: %{customdata[1]}<extra></extra>"
                ),
            )
        )
    # Always keep the corridor and the hypo rule in frame — they are the reference
    # the whole chart is read against.
    low = min(df["glucose"].min(), HYPO, patient.target_fasting_min)
    high = max(df["glucose"].max(), patient.target_pp_max)
    headroom = max((high - low) * 0.12, 15)

    fig.update_layout(
        height=360,
        margin=dict(l=4, r=4, t=8, b=4),
        font=PLOT_FONT,
        yaxis=dict(title=None, gridcolor=HAIRLINE, zeroline=False, ticksuffix=" ",
                   range=[low - headroom, high + headroom],
                   tickfont=dict(family="IBM Plex Mono, monospace", size=10)),
        xaxis=dict(gridcolor="#f7f9fb", tickfont=dict(size=10)),
        plot_bgcolor="#ffffff",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, font=dict(size=11)),
        hoverlabel=dict(font=dict(family="IBM Plex Sans, sans-serif", size=12), bgcolor="#fff", bordercolor=LINE),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    left, right = st.columns([1.1, 1])
    with left:
        _distribution(df, patient)
    with right:
        _by_context(df)


def _distribution(df: pd.DataFrame, patient: PatientProfile) -> None:
    out = ~df["in_range"].fillna(True)
    low = int((out & (df["glucose"] < patient.target_fasting_min)).sum())
    high = int(out.sum()) - low
    inside = len(df) - low - high
    total = max(len(df), 1)

    st.markdown('<div class="gs-legend">Where the readings fell</div>', unsafe_allow_html=True)
    fig = go.Figure()
    for label, count, colour in (
        ("Below", low, BELOW),
        ("Inside", inside, INSIDE),
        ("Above", high, ABOVE),
    ):
        share = count / total * 100
        fig.add_trace(
            go.Bar(
                x=[share], y=[""], orientation="h", name=label, marker_color=colour,
                text=[f"{share:.0f}%" if share >= 14 else ""],
                textposition="inside", insidetextanchor="middle", textangle=0,
                textfont=dict(family="IBM Plex Mono, monospace", size=11, color="#fff"),
                hovertemplate=f"{label}: {count} of {len(df)} readings<extra></extra>",
            )
        )
    fig.update_layout(
        barmode="stack", height=92, margin=dict(l=0, r=0, t=6, b=0), font=PLOT_FONT,
        legend=dict(orientation="h", yanchor="top", y=-0.25, x=0, font=dict(size=11)),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _by_context(df: pd.DataFrame) -> None:
    st.markdown('<div class="gs-legend">Average by time of day</div>', unsafe_allow_html=True)
    grouped = df.groupby("label")["glucose"].agg(["mean", "count"]).reset_index()
    rows = "".join(
        f'<div style="display:flex;justify-content:space-between;padding:7px 0;'
        f'border-bottom:1px solid {HAIRLINE};font-size:13.5px;color:{GRAPHITE};">'
        f"<span>{r.label}</span>"
        f'<span class="gs-mono" style="color:{INK};font-weight:500;">{r.mean:.0f} '
        f'<span style="color:{MUTED};font-weight:400;font-size:11.5px;">mg/dL · {int(r.count)} readings</span></span>'
        f"</div>"
        for r in grouped.itertuples()
    )
    st.markdown(rows, unsafe_allow_html=True)


def _plan(repo: Repository, patient: PatientProfile) -> None:
    plans = repo.list_care_plans(patient.patient_id)
    if not plans:
        st.markdown(
            '<div class="gs-empty"><b>No care plan yet</b>'
            "Milestones added to this patient's plan will appear here.</div>",
            unsafe_allow_html=True,
        )
        return

    overdue = [p for p in plans if p.status.value == "OVERDUE"]
    if overdue:
        st.markdown(
            f'<div class="gs-legend" style="color:{BELOW};margin-bottom:8px;">'
            f"{len(overdue)} overdue</div>",
            unsafe_allow_html=True,
        )
    rows = []
    for plan in plans:
        status = plan.status.value.title()
        tone = BELOW if plan.status.value == "OVERDUE" else INSIDE if plan.status.value == "COMPLETED" else SLATE
        done = plan.completed_date.strftime("%d %b %Y") if plan.completed_date else "—"
        rows.append(
            f'<div style="display:grid;grid-template-columns:1.6fr 110px 110px 110px;gap:14px;'
            f'padding:11px 0;border-bottom:1px solid {HAIRLINE};font-size:13.5px;align-items:center;">'
            f'<span style="color:{INK};font-weight:500;">{plan.title}</span>'
            f'<span class="gs-mono" style="color:{SLATE};font-size:12px;">{plan.target_date.strftime("%d %b %Y")}</span>'
            f'<span class="gs-legend" style="color:{tone};">{status}</span>'
            f'<span class="gs-mono" style="color:{MUTED};font-size:12px;">{done}</span>'
            f"</div>"
        )
    header = (
        f'<div style="display:grid;grid-template-columns:1.6fr 110px 110px 110px;gap:14px;'
        f'padding-bottom:7px;border-bottom:1px solid {LINE};">'
        '<span class="gs-legend">Milestone</span><span class="gs-legend">Due</span>'
        '<span class="gs-legend">Status</span><span class="gs-legend">Done</span></div>'
    )
    st.markdown(header + "".join(rows), unsafe_allow_html=True)


def _thread(repo: Repository, patient: PatientProfile) -> None:
    messages = repo.list_messages(patient.patient_id, limit=30)
    if not messages:
        st.markdown(
            '<div class="gs-empty"><b>No messages yet</b>'
            f"Nothing has been exchanged with {patient.full_name} on WhatsApp.</div>",
            unsafe_allow_html=True,
        )
        return
    blocks = []
    for msg in reversed(messages):
        outbound = msg["direction"] == "OUT"
        who = "Care team" if outbound else patient.full_name
        stamp = (msg["created_at"] or "")[:16].replace("T", " ")
        css = "gs-out" if outbound else "gs-in"
        blocks.append(
            f'<div class="gs-stamp">{who} · {stamp}</div>'
            f'<div class="{css}">{msg["content"]}</div>'
        )
    st.markdown("".join(blocks), unsafe_allow_html=True)


def _alerts(repo: Repository, patient: PatientProfile) -> None:
    from ui.components.alerts import render_alert

    tickets = [
        t
        for t in repo.list_tickets()
        if t.patient_id == patient.patient_id
        and t.status in {ActionStatus.PENDING, ActionStatus.AUTO_DISPATCHED}
    ]
    if not tickets:
        st.markdown(
            '<div class="gs-empty"><b>Nothing open</b>'
            f"{patient.full_name} has no alerts waiting for a clinician.</div>",
            unsafe_allow_html=True,
        )
        return
    for ticket in tickets:
        tone = PRIORITY_TONE[ticket.priority]
        st.markdown(
            f'<div class="gs-legend" style="color:{tone};margin-top:6px;">'
            f"{PRIORITY_LABEL[ticket.priority]} — {ticket.triage_reason}</div>",
            unsafe_allow_html=True,
        )
        render_alert(repo, ticket, patient, compact=True, key_prefix="record")
