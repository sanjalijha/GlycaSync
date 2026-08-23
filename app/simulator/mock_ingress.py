"""Edge testing harness — simulates WhatsApp voice/image/text payloads."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from app.agents.graph import run_ingress_graph
from app.config import get_settings
from app.db.seed_data import ensure_seeded


@dataclass
class Scenario:
    key: str
    title: str
    patient_id: str
    phone_number: str
    text: str
    image_name: Optional[str]
    audio_name: Optional[str]
    expected_priority: str
    narrative: str


SCENARIOS: list[Scenario] = [
    Scenario(
        key="p1",
        title="High reading with symptoms — photo plus Hindi voice note",
        patient_id="P-1001",
        phone_number="+919811000001",
        text="Khane ke baad mera sugar aaj bohot high lag raha hai, aur thodi ghabrahat ho rahi hai.",
        image_name="glucometer_245.png",
        audio_name="voice_high_245.hint",
        expected_priority="P1_ESCALATION",
        narrative="245 mg/dL after a meal with palpitations. Queued for clinician review.",
    ),
    Scenario(
        key="p0",
        title="Severe low blood sugar",
        patient_id="P-1010",
        phone_number="+919820000010",
        text="Feeling very shaky.",
        image_name="glucometer_048.png",
        audio_name=None,
        expected_priority="P0_CRITICAL",
        narrative="48 mg/dL with shakiness. Standard safety guidance goes out immediately.",
    ),
    Scenario(
        key="p2",
        title="Routine in-range fasting reading",
        patient_id="P-1009",
        phone_number="+919447000009",
        text="This morning's fasting is 118, I am feeling fine.",
        image_name="glucometer_118.png",
        audio_name=None,
        expected_priority="P2_ROUTINE",
        narrative="Within target. Recorded to the chart without raising an alert.",
    ),
    Scenario(
        key="p3",
        title="Unreadable meter photo",
        patient_id="P-1005",
        phone_number="+919825000005",
        text="machine pe kuch error aa raha hai",
        image_name="glucometer_error.png",
        audio_name=None,
        expected_priority="P3_UNCLEAR",
        narrative="Unreadable media / E-1 → clarification prompt.",
    ),
]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def render_glucometer(path: Path, value: Optional[int], error: Optional[str] = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (640, 400), "#1a2332")
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((40, 36, 600, 364), radius=28, fill="#0d141f", outline="#3d9b8f", width=4)
    draw.rounded_rectangle((90, 80, 550, 230), radius=12, fill="#d8efe6")
    if error:
        draw.text((150, 125), error, fill="#8b1e1e", font=_font(72))
        draw.text((120, 250), "STRIP / DEVICE ERROR", fill="#c9d6cf", font=_font(22))
    else:
        label = f"{value:03d}" if value is not None else "---"
        draw.text((200, 110), label, fill="#14332c", font=_font(90))
        draw.text((400, 190), "mg/dL", fill="#2f6b5f", font=_font(24))
        draw.text((120, 260), "Accu-Check  ·  MEM  ·  07:42", fill="#9bb8b0", font=_font(20))
    img.save(path)
    return path


def ensure_static_assets() -> Path:
    static = get_settings().static_dir
    render_glucometer(static / "glucometer_245.png", 245)
    render_glucometer(static / "glucometer_048.png", 48)
    render_glucometer(static / "glucometer_118.png", 118)
    render_glucometer(static / "glucometer_error.png", None, error="E-1")
    hint = static / "voice_high_245.hint"
    if not hint.exists():
        hint.write_text("Hindi voice-note stub for Sarvam Saaras offline path.\n", encoding="utf-8")
    return static


def run_scenario(key: str) -> dict:
    ensure_seeded()
    static = ensure_static_assets()
    scenario = next((s for s in SCENARIOS if s.key == key), None)
    if not scenario:
        raise ValueError(f"Unknown scenario '{key}'. Choose from: {[s.key for s in SCENARIOS]}")
    image_url = str(static / scenario.image_name) if scenario.image_name else None
    audio_url = str(static / scenario.audio_name) if scenario.audio_name else None
    result = run_ingress_graph(
        phone_number=scenario.phone_number,
        patient_id=scenario.patient_id,
        raw_text=scenario.text,
        image_url=image_url,
        audio_url=audio_url,
    )
    result["scenario"] = scenario.key
    result["expected_priority"] = scenario.expected_priority
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="GlycaSync WhatsApp ingress simulator")
    parser.add_argument(
        "--scenario",
        choices=[s.key for s in SCENARIOS] + ["all"],
        default="all",
        help="Clinical demo scenario to run",
    )
    args = parser.parse_args()
    keys = [s.key for s in SCENARIOS] if args.scenario == "all" else [args.scenario]
    for key in keys:
        result = run_scenario(key)
        print(
            f"[{key}] priority={result.get('priority')} "
            f"ticket={result.get('ticket_id')} auto={result.get('auto_dispatched')} "
            f"glucose={(result.get('extracted') or {}).get('blood_glucose_mg_dl')}"
        )
        print(f"      reason={result.get('triage_reason')}")


if __name__ == "__main__":
    main()
