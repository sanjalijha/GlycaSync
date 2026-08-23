"""LangGraph state machine: transcribe → extract → triage → synthesize → persist/dispatch."""

from __future__ import annotations

from typing import Optional, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.agents.extractor import extract_observation
from app.agents.synthesizer import synthesize_reply
from app.agents.triage import TriageResult, triage_observation
from app.db.database import Repository, get_repo
from app.integrations.sarvam import SarvamClient
from app.integrations.twilio_wa import WhatsAppGateway
from app.models.patient import PatientProfile
from app.models.triage import ActionStatus, PriorityLevel, TicketType, TriageTicket
from app.models.vitals import ExtractedObservation, VitalsLog, utcnow


class AgentState(TypedDict, total=False):
    phone_number: str
    patient_id: str
    raw_text: str
    audio_url: Optional[str]
    image_url: Optional[str]
    preferred_language: str
    transcript: str
    translated_text: str
    extracted: dict
    priority: str
    triage_reason: str
    circuit_breaker: bool
    emergency_english: str
    drafted_response: str
    drafted_response_localized: str
    ticket_id: Optional[str]
    log_id: Optional[str]
    auto_dispatched: bool
    skipped_ticket: bool
    error: Optional[str]


_sarvam = SarvamClient()


def _repo() -> Repository:
    return get_repo()


def _patient(state: AgentState) -> Optional[PatientProfile]:
    repo = _repo()
    if state.get("patient_id"):
        return repo.get_patient(state["patient_id"])
    if state.get("phone_number"):
        return repo.get_patient_by_phone(state["phone_number"])
    return None


def transcribe_node(state: AgentState) -> AgentState:
    patient = _patient(state)
    lang = (patient.preferred_language if patient else state.get("preferred_language")) or "hi"
    transcript = state.get("raw_text") or ""
    if state.get("audio_url"):
        spoken = _sarvam.transcribe(state["audio_url"], hint_language=lang)
        if spoken:
            transcript = (transcript + "\n" + spoken).strip()
    translated = _sarvam.translate_to_english(transcript, lang) if transcript else ""
    updates: AgentState = {
        "transcript": transcript,
        "translated_text": translated,
        "preferred_language": lang,
    }
    if patient:
        updates["patient_id"] = patient.patient_id
        updates["phone_number"] = patient.phone_number
    return updates


def extract_node(state: AgentState) -> AgentState:
    patient = _patient(state)
    if not patient:
        return {"error": "Unknown patient for this phone number."}
    text = state.get("translated_text") or state.get("transcript") or state.get("raw_text") or ""
    image_url = state.get("image_url")
    modality = "text"
    if image_url and (state.get("audio_url") or state.get("raw_text")):
        modality = "multimodal"
    elif image_url:
        modality = "image"
    elif state.get("audio_url"):
        modality = "voice"
    obs = extract_observation(patient, text=text, image_url=image_url, modality=modality)
    obs.raw_transcript = state.get("transcript") or text
    obs.translated_text = state.get("translated_text") or None
    return {"extracted": obs.model_dump(mode="json"), "patient_id": patient.patient_id}


def triage_node(state: AgentState) -> AgentState:
    patient = _patient(state)
    if not patient or not state.get("extracted"):
        return {"error": state.get("error") or "Missing extraction."}
    obs = ExtractedObservation.model_validate(state["extracted"])
    result: TriageResult = triage_observation(patient, obs)
    return {
        "priority": result.priority.value,
        "triage_reason": result.reason,
        "circuit_breaker": result.circuit_breaker,
        "emergency_english": result.emergency_english,
    }


def synthesize_node(state: AgentState) -> AgentState:
    patient = _patient(state)
    if not patient or not state.get("extracted"):
        return {}
    obs = ExtractedObservation.model_validate(state["extracted"])
    triage = TriageResult(
        priority=PriorityLevel(state["priority"]),
        reason=state.get("triage_reason") or "",
        circuit_breaker=bool(state.get("circuit_breaker")),
        emergency_english=state.get("emergency_english") or "",
    )
    english, localized = synthesize_reply(patient, obs, triage)
    return {
        "drafted_response": english,
        "drafted_response_localized": localized,
    }


def persist_node(state: AgentState) -> AgentState:
    patient = _patient(state)
    if not patient or not state.get("extracted"):
        return {"error": state.get("error") or "Cannot persist incomplete state."}

    repo = _repo()
    obs = ExtractedObservation.model_validate(state["extracted"])
    priority = PriorityLevel(state["priority"])
    log_id = f"obs-{uuid4().hex[:12]}"
    if obs.blood_glucose_mg_dl is not None or obs.device_error:
        repo.insert_vital(
            VitalsLog(
                **obs.model_dump(),
                log_id=log_id,
                source="whatsapp",
            )
        )

    create_ticket = priority != PriorityLevel.P2_ROUTINE
    ticket_id = None
    auto_dispatched = False
    gateway = WhatsAppGateway(repo)

    if state.get("circuit_breaker") and state.get("drafted_response"):
        ticket_id = f"T-P0-{uuid4().hex[:8]}"
        repo.insert_ticket(
            TriageTicket(
                ticket_id=ticket_id,
                patient_id=patient.patient_id,
                priority=priority,
                extracted_data=obs,
                triage_reason=state.get("triage_reason") or "",
                drafted_response=state.get("drafted_response") or "",
                drafted_response_localized=state.get("drafted_response_localized") or "",
                status=ActionStatus.AUTO_DISPATCHED,
                ticket_type=TicketType.EMERGENCY,
                created_at=utcnow(),
                dispatched_message=state.get("drafted_response_localized") or state.get("drafted_response"),
            )
        )
        gateway.send_text(
            patient.phone_number,
            state.get("drafted_response_localized") or state["drafted_response"],
            patient_id=patient.patient_id,
            language=patient.preferred_language,
            ticket_id=ticket_id,
        )
        auto_dispatched = True
        create_ticket = False

    if create_ticket:
        ticket_id = f"T-{uuid4().hex[:8]}"
        repo.insert_ticket(
            TriageTicket(
                ticket_id=ticket_id,
                patient_id=patient.patient_id,
                priority=priority,
                extracted_data=obs,
                triage_reason=state.get("triage_reason") or "",
                drafted_response=state.get("drafted_response") or "",
                drafted_response_localized=state.get("drafted_response_localized") or "",
                status=ActionStatus.PENDING,
                ticket_type=TicketType.INGRESS,
            )
        )

    if priority == PriorityLevel.P2_ROUTINE and state.get("drafted_response"):
        gateway.send_text(
            patient.phone_number,
            state.get("drafted_response_localized") or state["drafted_response"],
            patient_id=patient.patient_id,
            language=patient.preferred_language,
        )

    return {
        "ticket_id": ticket_id,
        "log_id": log_id,
        "auto_dispatched": auto_dispatched,
        "skipped_ticket": priority == PriorityLevel.P2_ROUTINE,
        "patient_id": patient.patient_id,
    }


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("transcribe", transcribe_node)
    graph.add_node("extract", extract_node)
    graph.add_node("triage", triage_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("persist", persist_node)
    graph.add_edge(START, "transcribe")
    graph.add_edge("transcribe", "extract")
    graph.add_edge("extract", "triage")
    graph.add_edge("triage", "synthesize")
    graph.add_edge("synthesize", "persist")
    graph.add_edge("persist", END)
    return graph.compile()


_compiled = None


def get_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled


def run_ingress_graph(
    *,
    phone_number: str = "",
    patient_id: str = "",
    raw_text: str = "",
    image_url: Optional[str] = None,
    audio_url: Optional[str] = None,
) -> AgentState:
    graph = get_graph()
    result = graph.invoke(
        {
            "phone_number": phone_number,
            "patient_id": patient_id,
            "raw_text": raw_text,
            "image_url": image_url,
            "audio_url": audio_url,
        }
    )
    return result


def dispatch_ticket(
    ticket_id: str,
    *,
    edited_english: Optional[str] = None,
    reviewer: str = "Care Coordinator",
    repo: Optional[Repository] = None,
) -> Optional[TriageTicket]:
    repo = repo or get_repo()
    ticket = repo.get_ticket(ticket_id)
    if not ticket:
        return None
    patient = repo.get_patient(ticket.patient_id)
    if not patient:
        return None
    english = edited_english if edited_english is not None else ticket.drafted_response
    localized = ticket.drafted_response_localized
    if edited_english is not None:
        localized = _sarvam.translate_from_english(edited_english, patient.preferred_language)
    gateway = WhatsAppGateway(repo)
    gateway.send_text(
        patient.phone_number,
        localized or english,
        patient_id=patient.patient_id,
        language=patient.preferred_language,
        ticket_id=ticket.ticket_id,
    )
    return repo.update_ticket(
        ticket_id,
        status=ActionStatus.APPROVED,
        drafted_response=english,
        drafted_response_localized=localized,
        reviewed_by=reviewer,
        dispatched_message=localized or english,
    )
