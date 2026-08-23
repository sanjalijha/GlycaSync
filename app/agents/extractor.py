"""Agent 1 — multimodal extractor (VLM + NLP) with a robust offline fallback."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

import httpx

from app.config import get_settings
from app.models.patient import PatientProfile
from app.models.vitals import ExtractedObservation, ReadingContext

logger = logging.getLogger(__name__)

SYMPTOM_LEXICON: dict[str, tuple[str, ...]] = {
    "palpitations": ("palpitation", "ghabrahat", "ghabrhat", "dhadkan", "anxious", "ghabra"),
    "dizziness": ("dizz", "chakkar", "chakar", "lightheaded", "light headed"),
    "nausea": ("nause", "ulti", "vomit", "qai"),
    "sweating": ("sweat", "diaphores", "pasina", "pasinaa"),
    "shakiness": ("shak", "kamp", "kampat", "tremor", "tharr"),
    "chest_pain": ("chest pain", "seene mein dard", "seene me dard", "chest ache"),
    "confusion": ("confus", "uljhan", "disorient"),
    "blurred_vision": ("blur", "dhundla", "dhundhla"),
    "thirst": ("thirst", "pyaas", "pyas"),
    "fatigue": ("fatigue", "thakaan", "thakan", "tired"),
    "headache": ("headache", "sir dard", "sir mein dard"),
    "shortness_of_breath": ("breathless", "saans", "short of breath", "dyspnea"),
    "unconscious": ("unconscious", "behosh", "fainted", "passed out"),
}

GLUCOSE_PATTERNS = [
    re.compile(r"(?:blood\s*)?(?:sugar|glucose|bs|fbs|ppbs|rbs|hgt)\D{0,16}(\d{2,3}(?:\.\d+)?)", re.I),
    re.compile(r"(\d{2,3}(?:\.\d+)?)\s*(?:mg/?d[lL]|mgdl|mg%)", re.I),
    re.compile(r"\b(\d{2,3})\s*(?:fasting|pp|post[- ]?prandial|random|bedtime)\b", re.I),
    re.compile(r"\b(?:fasting|pp|post[- ]?prandial|random|bedtime)\D{0,8}(\d{2,3})\b", re.I),
    re.compile(r"(?:padh(?:a|i)?|dikha(?:ya)?|aa(?:ya|rahi)?)\D{0,12}(\d{2,3})", re.I),
]


def _detect_context(text: str) -> ReadingContext:
    blob = text.lower()
    if any(k in blob for k in ("fasting", "subah", "subah ka", "empty stomach", "khali pet", "fbs")):
        return ReadingContext.FASTING
    if any(k in blob for k in ("post", "pp", "after meal", "khane ke baad", "khaney", "ppbs")):
        return ReadingContext.POST_PRANDIAL
    if any(k in blob for k in ("bedtime", "raat", "before bed", "hs")):
        return ReadingContext.BEDTIME
    return ReadingContext.RANDOM


def _detect_symptoms(text: str) -> list[str]:
    blob = text.lower()
    found: list[str] = []
    for label, needles in SYMPTOM_LEXICON.items():
        if any(n in blob for n in needles):
            found.append(label)
    return found


def _detect_device_error(text: str) -> Optional[str]:
    upper = text.upper()
    if re.search(r"\bE-?1\b", upper):
        return "E-1"
    if re.search(r"\bE-?2\b", upper):
        return "E-2"
    if re.search(r"\bLOW[_\s-]?BATTERY\b", upper):
        return "LOW_BATTERY"
    if re.search(r"\bHI\b", upper):
        return "HI"
    if re.search(r"\bLO\b", upper):
        return "LO"
    return None


def _glucose_from_filename(image_url: Optional[str]) -> Optional[float]:
    if not image_url:
        return None
    match = re.search(r"glucometer[_-]?(\d{2,3})", Path(image_url).name, re.I)
    if match:
        return float(match.group(1))
    if "error" in Path(image_url).name.lower():
        return None
    return None


def _parse_glucose(text: str) -> Optional[float]:
    for pattern in GLUCOSE_PATTERNS:
        match = pattern.search(text)
        if match:
            value = float(match.group(1))
            if 20 <= value <= 700:
                return value
    # last resort: isolated 2–3 digit number near clinical words
    if re.search(r"sugar|glucose|glucometer|reading|mg", text, re.I):
        lonely = re.findall(r"\b(\d{2,3})\b", text)
        for token in lonely:
            value = float(token)
            if 40 <= value <= 600:
                return value
    return None


def _rule_extract(
    patient: PatientProfile,
    text: str,
    image_url: Optional[str],
    modality: str,
) -> ExtractedObservation:
    glucose = _parse_glucose(text)
    file_glucose = _glucose_from_filename(image_url)
    notes: list[str] = []
    if glucose is None and file_glucose is not None:
        glucose = file_glucose
        notes.append(f"Vision mock from media filename ({file_glucose:g} mg/dL).")
    elif glucose is not None and file_glucose is not None and abs(glucose - file_glucose) > 15:
        notes.append(f"Text {glucose:g} vs image hint {file_glucose:g}; preferring text.")
    elif file_glucose is not None:
        notes.append("Image filename consistent with parsed value.")

    error = _detect_device_error(text)
    if image_url and "error" in Path(image_url).name.lower():
        error = error or "E-1"
        notes.append("Media tagged as unreadable / device error.")

    symptoms = _detect_symptoms(text)
    context = _detect_context(text)

    if error and glucose is None:
        confidence = 0.28
        notes.append(f"Device error {error}; no numeric reading.")
    elif glucose is None:
        confidence = 0.35 if text.strip() else 0.15
        notes.append("No glucose value extracted.")
    elif symptoms:
        confidence = 0.94
    else:
        confidence = 0.90 if image_url else 0.86

    if not text.strip() and glucose is None:
        confidence = 0.12

    return ExtractedObservation(
        patient_id=patient.patient_id,
        blood_glucose_mg_dl=glucose,
        reading_context=context,
        symptoms=symptoms,
        confidence_score=round(confidence, 2),
        raw_transcript=text or None,
        image_url=image_url,
        extraction_notes="; ".join(notes) or "Rule-based extraction.",
        device_error=error,
        modality=modality,
    )


def _llm_extract(
    patient: PatientProfile,
    text: str,
    image_url: Optional[str],
) -> Optional[ExtractedObservation]:
    settings = get_settings()
    if not settings.llm_enabled:
        return None

    schema_hint = {
        "blood_glucose_mg_dl": "number or null",
        "reading_context": "FASTING|POST_PRANDIAL|RANDOM|BEDTIME",
        "symptoms": ["string"],
        "confidence_score": "0-1",
        "device_error": "E-1|HI|LO|LOW_BATTERY|null",
        "extraction_notes": "short",
    }
    prompt = (
        "You are a clinical entity extractor for Indian diabetes WhatsApp ingress. "
        "Extract ONLY structured fields. Never diagnose or advise. "
        f"Patient targets: fasting {patient.target_fasting_min}-{patient.target_fasting_max}, "
        f"PP max {patient.target_pp_max}. Text:\n{text}\n"
        f"Return JSON keys: {json.dumps(schema_hint)}"
    )
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    user_content: list[dict] = [{"type": "text", "text": prompt}]
    model = settings.llm_model
    if image_url and not image_url.startswith("ui/"):
        user_content.append({"type": "image_url", "image_url": {"url": image_url}})
        model = settings.llm_vision_model
    body = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "Extract glucose, context, symptoms. JSON only."},
            {"role": "user", "content": user_content},
        ],
    }
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    try:
        response = httpx.post(url, headers=headers, json=body, timeout=40)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM extraction failed: %s", exc)
        return None

    context_raw = str(data.get("reading_context") or "RANDOM").upper()
    try:
        context = ReadingContext(context_raw)
    except ValueError:
        context = _detect_context(text)
    glucose = data.get("blood_glucose_mg_dl")
    try:
        glucose_f = float(glucose) if glucose is not None else None
    except (TypeError, ValueError):
        glucose_f = None
    return ExtractedObservation(
        patient_id=patient.patient_id,
        blood_glucose_mg_dl=glucose_f,
        reading_context=context,
        symptoms=list(data.get("symptoms") or []),
        confidence_score=float(data.get("confidence_score") or 0.8),
        raw_transcript=text or None,
        image_url=image_url,
        extraction_notes=data.get("extraction_notes") or "LLM extraction",
        device_error=data.get("device_error"),
        modality="multimodal" if image_url else "text",
    )


def extract_observation(
    patient: PatientProfile,
    *,
    text: str = "",
    image_url: Optional[str] = None,
    modality: str = "text",
) -> ExtractedObservation:
    llm = _llm_extract(patient, text, image_url)
    if llm and (llm.blood_glucose_mg_dl is not None or llm.device_error):
        llm.modality = modality
        return llm
    return _rule_extract(patient, text, image_url, modality)
