from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PatientProfile(BaseModel):
    patient_id: str
    full_name: str
    phone_number: str
    preferred_language: str = "hi"  # ISO 639-1: hi, mr, ta, te, en
    target_fasting_min: float = 80.0
    target_fasting_max: float = 130.0
    target_pp_max: float = 180.0
    last_hba1c_date: Optional[datetime] = None
    last_hba1c_value: Optional[float] = None
    last_log_timestamp: Optional[datetime] = None
    last_consult_date: Optional[datetime] = None
    abha_id: Optional[str] = None
    age: int = 50
    sex: str = "M"
    city: str = "Mumbai"
    diabetes_type: str = "T2DM"
    insulin_dependent: bool = False
    medications: List[str] = Field(default_factory=list)
    emergency_contact: str = ""
    emergency_phone: str = ""
    literacy_note: str = "standard"
    notes: str = ""
