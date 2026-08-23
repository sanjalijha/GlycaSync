from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReadingContext(str, Enum):
    FASTING = "FASTING"
    POST_PRANDIAL = "POST_PRANDIAL"
    RANDOM = "RANDOM"
    BEDTIME = "BEDTIME"


class ExtractedObservation(BaseModel):
    patient_id: str
    timestamp: datetime = Field(default_factory=utcnow)
    blood_glucose_mg_dl: Optional[float] = None
    reading_context: ReadingContext = ReadingContext.RANDOM
    symptoms: List[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    raw_transcript: Optional[str] = None
    translated_text: Optional[str] = None
    image_url: Optional[str] = None
    extraction_notes: Optional[str] = None
    device_error: Optional[str] = None  # E-1, HI, LO, LOW_BATTERY
    modality: str = "text"  # text | voice | image | multimodal


class VitalsLog(ExtractedObservation):
    """FHIR Observation equivalent persisted to vitals_logs."""

    log_id: str
    resource_type: str = "Observation"
    unit: str = "mg/dL"
    source: str = "whatsapp"
