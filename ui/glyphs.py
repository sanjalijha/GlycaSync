"""The corridor trace: a patient's recent readings drawn against their own targets.

This is the console's signature mark. A flat line resting inside the shaded band
means the patient is holding their range; spikes above it, or dips below the
hypo rule, are legible without reading a single number.
"""

from __future__ import annotations

from typing import Optional, Sequence

from app.models.patient import PatientProfile
from ui.design import ABOVE, BELOW, INK, INSIDE, LINE, QUIET

# A shared vertical scale keeps every trace on the panel directly comparable, kept
# tight enough that a typical corridor still fills a readable share of the height.
SCALE_MIN = 50.0
SCALE_MAX = 320.0
HYPO = 70.0

# Enough points to show a pattern, few enough that each one stays separable.
MAX_POINTS = 16


def _y(value: float, height: float, pad: float) -> float:
    span = SCALE_MAX - SCALE_MIN
    clamped = max(SCALE_MIN, min(SCALE_MAX, value))
    return pad + (SCALE_MAX - clamped) / span * (height - 2 * pad)


def ceiling_for(patient: PatientProfile, context: Optional[object]) -> float:
    """The upper limit that applies to a reading taken in this context."""
    value = getattr(context, "value", context)
    if value == "FASTING":
        return patient.target_fasting_max
    return patient.target_pp_max


def reading_tone(
    patient: Optional[PatientProfile],
    value: Optional[float],
    context: Optional[object] = None,
) -> str:
    if value is None or patient is None:
        return QUIET
    if value < HYPO or value < patient.target_fasting_min:
        return BELOW
    if value > ceiling_for(patient, context):
        return ABOVE
    return INSIDE


def corridor_trace(
    patient: PatientProfile,
    readings: Sequence[tuple[float, str]],
    *,
    width: int = 208,
    height: int = 48,
) -> str:
    """Inline SVG sparkline of recent readings over the patient's target corridor."""
    pad = 5.0
    readings = list(readings)[-MAX_POINTS:]
    values = [value for value, _ in readings]
    if not values:
        return (
            f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'role="img" aria-label="No readings recorded">'
            f'<line x1="0" y1="{height / 2}" x2="{width}" y2="{height / 2}" '
            f'stroke="{LINE}" stroke-width="1" stroke-dasharray="2 3"/>'
            f'<text x="{width / 2}" y="{height / 2 + 11}" text-anchor="middle" '
            f'font-family="IBM Plex Mono, monospace" font-size="9" fill="{QUIET}">no readings</text>'
            f"</svg>"
        )

    top = _y(patient.target_pp_max, height, pad)
    bottom = _y(patient.target_fasting_min, height, pad)
    hypo_y = _y(HYPO, height, pad)

    step = (width - 2 * pad) / max(len(values) - 1, 1)
    points = [(pad + i * step, _y(v, height, pad)) for i, v in enumerate(values)]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)

    marks = []
    for (x, y), (value, context) in zip(points[:-1], readings[:-1]):
        tone = reading_tone(patient, value, context)
        if tone != INSIDE:
            marks.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.2" fill="{tone}" opacity="0.9"/>')

    last_x, last_y = points[-1]
    last_tone = reading_tone(patient, *readings[-1])
    marks.append(
        f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="4.2" fill="#fff"/>'
        f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="2.8" fill="{last_tone}"/>'
    )

    label = (
        f"{len(values)} readings, latest {values[-1]:.0f} milligrams per decilitre, "
        f"target {patient.target_fasting_min:.0f} to {patient.target_pp_max:.0f}"
    )
    band = max(bottom - top, 1)
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{label}">'
        f'<rect x="0" y="{top:.1f}" width="{width}" height="{band:.1f}" '
        f'fill="{INSIDE}" opacity="0.15"/>'
        f'<line x1="0" y1="{top:.1f}" x2="{width}" y2="{top:.1f}" '
        f'stroke="{INSIDE}" stroke-width="1" opacity="0.5"/>'
        f'<line x1="0" y1="{bottom:.1f}" x2="{width}" y2="{bottom:.1f}" '
        f'stroke="{INSIDE}" stroke-width="1" opacity="0.5"/>'
        f'<line x1="0" y1="{hypo_y:.1f}" x2="{width}" y2="{hypo_y:.1f}" '
        f'stroke="{BELOW}" stroke-width="1" stroke-dasharray="2 3" opacity="0.5"/>'
        f'<polyline points="{path}" fill="none" stroke="{INK}" stroke-width="1.5" '
        f'stroke-opacity="0.6" stroke-linejoin="round" stroke-linecap="round"/>'
        f'{"".join(marks)}'
        f"</svg>"
    )
