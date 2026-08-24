"""WhatsApp webhook for Twilio (Vercel) plus optional local portal REST.

On Vercel only the webhook and a thin health check are exposed. The care-team
REST API stays available for local uvicorn and tests.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.database import get_repo
from app.db.seed_data import ensure_seeded
from app.integrations.debounce import DebounceBuffer, IngressPart
from app.integrations.twilio_wa import (
    fetch_inbound_media,
    log_inbound,
    parse_twilio_inbound,
    validate_twilio_signature,
)

logger = logging.getLogger(__name__)

# Vercel sets this automatically. Local uvicorn / pytest leave it unset.
ON_VERCEL = bool(os.environ.get("VERCEL"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_seeded()
    yield


app = FastAPI(
    title="GlycaSync WhatsApp webhook",
    description="Twilio WhatsApp ingress for GlycaSync. Portal REST is local-only.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if ON_VERCEL else "/docs",
    redoc_url=None if ON_VERCEL else "/redoc",
    openapi_url=None if ON_VERCEL else "/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _process_composite(payload) -> dict:
    from app.agents.graph import run_ingress_graph

    return run_ingress_graph(
        phone_number=payload.phone_number,
        raw_text=payload.text,
        image_url=payload.image_url,
        audio_url=payload.audio_url,
    )


debounce = DebounceBuffer(
    window_seconds=get_settings().debounce_seconds,
    on_flush=_process_composite,
)

EMPTY_TWIML = "<?xml version='1.0' encoding='UTF-8'?><Response></Response>"


@app.get("/")
def root() -> dict:
    settings = get_settings()
    payload = {
        "app": settings.app_name,
        "status": "ok",
        "role": "whatsapp-webhook" if ON_VERCEL else "full-api",
        "health": "/health",
        "webhook": "/webhook/whatsapp",
    }
    if not ON_VERCEL:
        payload["docs"] = "/docs"
    return payload


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    repo = get_repo()
    return {
        "status": "ok",
        "app": settings.app_name,
        "clinic": settings.clinic_name,
        "patients": repo.patient_count(),
        "database": str(repo.db_path),
        "llm": settings.llm_enabled,
        "sarvam": settings.sarvam_enabled,
        "twilio": settings.twilio_enabled,
        "webhook_url": settings.webhook_url,
        "signature_check": settings.twilio_validate_signature and settings.twilio_enabled,
        "debounce_pending": debounce.pending_count(),
        "vercel": ON_VERCEL,
    }


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


if not ON_VERCEL:
    from app.portal_api import mount_portal_api

    mount_portal_api(app, debounce=debounce)
