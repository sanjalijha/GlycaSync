"""Care-team REST routes — local/dev only. Not mounted on Vercel."""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.agents.auditor import audit_emr
from app.agents.graph import dispatch_ticket, run_ingress_graph
from app.config import get_settings
from app.db.database import get_repo
from app.integrations.debounce import IngressPart
from app.integrations.twilio_wa import WhatsAppGateway
from app.models.triage import ActionStatus


class SimulateIngress(BaseModel):
    phone_number: str = ""
    patient_id: str = ""
    text: str = ""
    image_url: Optional[str] = None
    audio_url: Optional[str] = None
    debounce: bool = False


class DispatchBody(BaseModel):
    edited_english: Optional[str] = None
    reviewer: str = "Care Coordinator"


def mount_portal_api(app: FastAPI, *, debounce) -> None:
    """Attach the full portal REST surface used by local uvicorn and tests."""

    @app.post("/api/ingress/simulate")
    async def simulate_ingress(body: SimulateIngress) -> dict:
        if body.debounce and body.phone_number:
            await debounce.add(
                IngressPart(
                    phone_number=body.phone_number,
                    text=body.text,
                    image_url=body.image_url,
                    audio_url=body.audio_url,
                )
            )
            return {"queued": True, "window_seconds": get_settings().debounce_seconds}
        return run_ingress_graph(
            phone_number=body.phone_number,
            patient_id=body.patient_id,
            raw_text=body.text,
            image_url=body.image_url,
            audio_url=body.audio_url,
        )

    @app.get("/api/patients")
    def list_patients() -> list[dict]:
        return [p.model_dump(mode="json") for p in get_repo().list_patients()]

    @app.get("/api/patients/{patient_id}")
    def get_patient(patient_id: str) -> dict:
        patient = get_repo().get_patient(patient_id)
        if not patient:
            raise HTTPException(404, "Patient not found")
        return patient.model_dump(mode="json")

    @app.get("/api/patients/{patient_id}/vitals")
    def get_vitals(patient_id: str) -> list[dict]:
        return [v.model_dump(mode="json") for v in get_repo().list_vitals(patient_id)]

    @app.get("/api/patients/{patient_id}/care-plans")
    def get_care_plans(patient_id: str) -> list[dict]:
        return [c.model_dump(mode="json") for c in get_repo().list_care_plans(patient_id)]

    @app.get("/api/patients/{patient_id}/messages")
    def get_messages(patient_id: str) -> list[dict]:
        return get_repo().list_messages(patient_id)

    @app.get("/api/tickets")
    def list_tickets(status: Optional[str] = None, ticket_type: Optional[str] = None) -> list[dict]:
        return [
            t.model_dump(mode="json")
            for t in get_repo().list_tickets(status=status, ticket_type=ticket_type)
        ]

    @app.post("/api/tickets/{ticket_id}/dispatch")
    def api_dispatch(ticket_id: str, body: DispatchBody) -> dict:
        ticket = dispatch_ticket(
            ticket_id, edited_english=body.edited_english, reviewer=body.reviewer
        )
        if not ticket:
            raise HTTPException(404, "Ticket not found")
        return ticket.model_dump(mode="json")

    @app.post("/api/tickets/{ticket_id}/resolve")
    def api_resolve(ticket_id: str) -> dict:
        ticket = get_repo().update_ticket(
            ticket_id, status=ActionStatus.RESOLVED, reviewed_by="Care Coordinator"
        )
        if not ticket:
            raise HTTPException(404, "Ticket not found")
        return ticket.model_dump(mode="json")

    @app.post("/api/auditor/run")
    def run_auditor() -> dict:
        created = audit_emr()
        return {"created": [t.model_dump(mode="json") for t in created], "count": len(created)}

    @app.get("/api/outbox")
    def outbox() -> list[dict]:
        return WhatsAppGateway().recent_outbox()

    @app.get("/api/stats")
    def stats() -> dict:
        return get_repo().dashboard_counts()
