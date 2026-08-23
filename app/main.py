"""FastAPI ingress webhooks and REST API for the care-team portal."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agents.auditor import audit_emr
from app.agents.graph import dispatch_ticket, run_ingress_graph
from app.config import get_settings
from app.db.database import get_repo
from app.db.seed_data import ensure_seeded
from app.integrations.debounce import DebounceBuffer, IngressPart
from app.integrations.twilio_wa import (
    WhatsAppGateway,
    fetch_inbound_media,
    log_inbound,
    parse_twilio_inbound,
    validate_twilio_signature,
)
from app.models.triage import ActionStatus

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_seeded()
    yield


app = FastAPI(
    title="GlycaSync API",
    description="Assistive diabetes care orchestration — extraction, triage, human-in-the-loop dispatch.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _process_composite(payload) -> dict:
    return run_ingress_graph(
        phone_number=payload.phone_number,
        raw_text=payload.text,
        image_url=payload.image_url,
        audio_url=payload.audio_url,
    )


debounce = DebounceBuffer(window_seconds=get_settings().debounce_seconds, on_flush=_process_composite)


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    repo = get_repo()
    return {
        "status": "ok",
        "app": settings.app_name,
        "clinic": settings.clinic_name,
        "patients": repo.patient_count(),
        "llm": settings.llm_enabled,
        "sarvam": settings.sarvam_enabled,
        "twilio": settings.twilio_enabled,
        "webhook_url": settings.webhook_url,
        "signature_check": settings.twilio_validate_signature and settings.twilio_enabled,
        "debounce_pending": debounce.pending_count(),
    }


class SimulateIngress(BaseModel):
    phone_number: str = ""
    patient_id: str = ""
    text: str = ""
    image_url: Optional[str] = None
    audio_url: Optional[str] = None
    debounce: bool = False


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
    result = run_ingress_graph(
        phone_number=body.phone_number,
        patient_id=body.patient_id,
        raw_text=body.text,
        image_url=body.image_url,
        audio_url=body.audio_url,
    )
    return result


EMPTY_TWIML = "<?xml version='1.0' encoding='UTF-8'?><Response></Response>"


@app.post("/webhook/whatsapp")
async def twilio_webhook(request: Request) -> Response:
    """Receive a WhatsApp message from Twilio.

    Answers with empty TwiML: the reply is drafted, triaged and usually reviewed by a
    clinician before it goes out, so nothing is said in the webhook response itself.
    """
    form = dict(await request.form())

    settings = get_settings()
    if settings.twilio_validate_signature and settings.twilio_enabled:
        signature = request.headers.get("X-Twilio-Signature", "")
        if not validate_twilio_signature(signature, str(request.url), form):
            logger.warning("Rejected an unsigned or missigned request to the WhatsApp webhook.")
            raise HTTPException(403, "Invalid Twilio signature")

    inbound = parse_twilio_inbound(form)
    if not inbound["phone_number"]:
        logger.warning("WhatsApp webhook received a payload with no sender; ignoring.")
        return Response(EMPTY_TWIML, media_type="text/xml")

    # Log the receive immediately — before debounce, and whether or not the
    # number is on a chart — so the thread shows what Twilio delivered.
    log_inbound(inbound)

    if not get_repo().get_patient_by_phone(inbound["phone_number"]):
        logger.warning(
            "WhatsApp message from unregistered number %s; not adding to any chart.",
            inbound["phone_number"],
        )
        return Response(EMPTY_TWIML, media_type="text/xml")

    if inbound["image_url"] or inbound["audio_url"]:
        inbound = await run_in_threadpool(fetch_inbound_media, inbound)

    await debounce.add(
        IngressPart(
            phone_number=inbound["phone_number"],
            text=inbound["text"],
            image_url=inbound["image_url"],
            audio_url=inbound["audio_url"],
        )
    )
    return Response(EMPTY_TWIML, media_type="text/xml")


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
    return [t.model_dump(mode="json") for t in get_repo().list_tickets(status=status, ticket_type=ticket_type)]


class DispatchBody(BaseModel):
    edited_english: Optional[str] = None
    reviewer: str = "Care Coordinator"


@app.post("/api/tickets/{ticket_id}/dispatch")
def api_dispatch(ticket_id: str, body: DispatchBody) -> dict:
    ticket = dispatch_ticket(ticket_id, edited_english=body.edited_english, reviewer=body.reviewer)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    return ticket.model_dump(mode="json")


@app.post("/api/tickets/{ticket_id}/resolve")
def api_resolve(ticket_id: str) -> dict:
    ticket = get_repo().update_ticket(ticket_id, status=ActionStatus.RESOLVED, reviewed_by="Care Coordinator")
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
