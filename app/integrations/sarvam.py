"""Sarvam AI adapter — Saaras STT + Mayura translation, with offline Indic stubs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Compact phrasebook used when SARVAM_API_KEY is absent, so the flow stays testable offline.
_PHRASEBOOK = {
    "hi": {
        "my sugar feels very high today, and i am feeling a bit anxious/palpitations.": (
            "Mera sugar aaj bohot high lag raha hai, aur thodi ghabrahat ho rahi hai."
        ),
        "feeling very shaky.": "Bahut kamp ho raha hai / shaky feel ho raha hai.",
        "feeling very shaky": "Bahut kamp ho raha hai.",
    },
    "mr": {
        "feeling very shaky.": "Khop khup kampat ahe.",
        "feeling very shaky": "Khop khup kampat ahe.",
    },
}

_ENGLISH_FROM_INDIC = {
    "mera sugar aaj bohot high lag raha hai, aur thodi ghabrahat ho rahi hai.": (
        "My sugar feels very high today, and I am feeling a bit anxious/palpitations."
    ),
    "bahut kamp ho raha hai / shaky feel ho raha hai.": "Feeling very shaky.",
    "bahut kamp ho raha hai.": "Feeling very shaky.",
    "khop khup kampat ahe.": "Feeling very shaky.",
    "machine pe kuch error aa raha hai": "There is some error showing on the machine.",
    "aaj subah ka fasting 118 hai, theek feel ho raha hai": (
        "This morning's fasting is 118, I am feeling fine."
    ),
}


class SarvamClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    def transcribe(self, audio_path: Optional[str], hint_language: str = "hi") -> str:
        """Saaras speech-to-text. Offline: return a language-appropriate stub from filename."""
        if not audio_path:
            return ""
        if self.settings.sarvam_enabled:
            try:
                return self._saaras_transcribe(audio_path, hint_language)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Sarvam STT failed, using stub: %s", exc)
        name = Path(audio_path).stem.lower()
        if "high" in name or "245" in name:
            return "Mera sugar aaj bohot high lag raha hai, aur thodi ghabrahat ho rahi hai."
        if "hypo" in name or "shaky" in name or "48" in name:
            return "Bahut kamp ho raha hai / shaky feel ho raha hai."
        if "ok" in name or "118" in name:
            return "Aaj subah ka fasting 118 hai, theek feel ho raha hai"
        return ""

    def translate_to_english(self, text: str, source_language: str = "hi") -> str:
        if not text:
            return ""
        if source_language in {"en", "eng"}:
            return text
        key = text.strip().lower()
        if key in _ENGLISH_FROM_INDIC:
            return _ENGLISH_FROM_INDIC[key]
        if self.settings.sarvam_enabled:
            try:
                return self._mayura_translate(text, source_language, "en")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Sarvam translate→en failed: %s", exc)
        return text

    def translate_from_english(self, text: str, target_language: str = "hi") -> str:
        if not text or target_language in {"en", "eng"}:
            return text
        if self.settings.sarvam_enabled:
            try:
                return self._mayura_translate(text, "en", target_language)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Sarvam translate←en failed: %s", exc)
        return _offline_localize(text, target_language)

    def _saaras_transcribe(self, audio_path: str, language: str) -> str:
        url = f"{self.settings.sarvam_base_url.rstrip('/')}/speech-to-text"
        headers = {"api-subscription-key": self.settings.sarvam_api_key}
        with Path(audio_path).open("rb") as handle:
            files = {"file": (Path(audio_path).name, handle, "audio/mpeg")}
            data = {"language_code": _sarvam_lang(language)}
            response = httpx.post(url, headers=headers, files=files, data=data, timeout=45)
        response.raise_for_status()
        payload = response.json()
        return payload.get("transcript") or payload.get("text") or ""

    def _mayura_translate(self, text: str, source: str, target: str) -> str:
        url = f"{self.settings.sarvam_base_url.rstrip('/')}/translate"
        headers = {
            "api-subscription-key": self.settings.sarvam_api_key,
            "Content-Type": "application/json",
        }
        body = {
            "input": text,
            "source_language_code": _sarvam_lang(source),
            "target_language_code": _sarvam_lang(target),
            "speaker_gender": "Male",
            "mode": "formal",
            "model": "mayura:v1",
            "enable_preprocessing": True,
        }
        response = httpx.post(url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        payload = response.json()
        return payload.get("translated_text") or payload.get("output") or text


def _sarvam_lang(code: str) -> str:
    mapping = {
        "hi": "hi-IN",
        "mr": "mr-IN",
        "ta": "ta-IN",
        "te": "te-IN",
        "en": "en-IN",
        "gu": "gu-IN",
        "bn": "bn-IN",
        "kn": "kn-IN",
        "ml": "ml-IN",
        "pa": "pa-IN",
    }
    return mapping.get(code, "hi-IN")


def _offline_localize(english: str, lang: str) -> str:
    """Best-effort template overlay for demo when Sarvam is offline."""
    prefixes = {
        "hi": "नमस्ते — ",
        "mr": "नमस्कार — ",
        "ta": "வணக்கம் — ",
        "te": "నమస్కారం — ",
    }
    closings = {
        "hi": "\n\n— GlycaSync देखभाल टीम",
        "mr": "\n\n— GlycaSync देखभाल टीम",
        "ta": "\n\n— GlycaSync பராமரிப்பு குழு",
        "te": "\n\n— GlycaSync సంరక్షణ బృందం",
    }
    prefix = prefixes.get(lang, "")
    closing = closings.get(lang, "\n\n— GlycaSync care team")
    phrasebook = _PHRASEBOOK.get(lang, {})
    for key, native in phrasebook.items():
        if key in english.lower():
            return prefix + native + closing
    return prefix + english + closing
