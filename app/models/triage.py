from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.models.vitals import ExtractedObservation, utcnow


class PriorityLevel(str, Enum):
    P0_CRITICAL = "P0_CRITICAL"
    P1_ESCALATION = "P1_ESCALATION"
    P2_ROUTINE = "P2_ROUTINE"
    P3_UNCLEAR = "P3_UNCLEAR"


class ActionStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RESOLVED = "RESOLVED"
    AUTO_DISPATCHED = "AUTO_DISPATCHED"


class TicketType(str, Enum):
    INGRESS = "INGRESS"
    OUTREACH = "OUTREACH"
    EMERGENCY = "EMERGENCY"


class TriageTicket(BaseModel):
    ticket_id: str
    patient_id: str
    priority: PriorityLevel
    extracted_data: ExtractedObservation
    triage_reason: str
    drafted_response: str
    drafted_response_localized: str = ""
    status: ActionStatus = ActionStatus.PENDING
    ticket_type: TicketType = TicketType.INGRESS
    created_at: datetime = Field(default_factory=utcnow)
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    dispatched_message: Optional[str] = None
