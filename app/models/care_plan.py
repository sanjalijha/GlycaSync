from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class MilestoneType(str, Enum):
    HBA1C = "HBA1C"
    CONSULT = "CONSULT"
    RETINAL = "RETINAL"
    FOOT_EXAM = "FOOT_EXAM"
    LIPID = "LIPID"


class MilestoneStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    OVERDUE = "OVERDUE"
    COMPLETED = "COMPLETED"


class CarePlanMilestone(BaseModel):
    plan_id: str
    patient_id: str
    milestone_type: MilestoneType
    title: str
    target_date: datetime
    completed_date: Optional[datetime] = None
    status: MilestoneStatus = MilestoneStatus.SCHEDULED
    notes: str = ""
