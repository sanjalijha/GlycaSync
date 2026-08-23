GlycaSync: Bidirectional Multi-Agent Diabetes Care Orchestrator
Target: Health-a-thon 2026 (Koita Foundation / IIT Bombay)
Track: Clinician & Care Team Facing (Diabetes Chronic Care Management)
Document Version: 2.0 (System Architecture & Technical Plan)

1. Executive Summary & Clinical Philosophy
GlycaSync is an assistive, closed-loop chronic care coordination platform designed specifically for Indian diabetes management. It bridges the critical gap between periodic clinic visits by operating along two synchronized vectors:
Proactive EMR Auditing (Outreach Vector): Continuously evaluates the EMR to detect missed milestones (overdue HbA1c tests, missing quarterly consultations, or prolonged logging drop-offs) and queues personalized, localized outreach nudges.
Reactive Multimodal Ingress & Triage (Care Ingress Vector): Ingests unstructured patient inputs via WhatsApp (Indic voice notes, text messages, photos of glucometer screens or lab slips), extracts structured clinical entities with confidence scoring, and routes flagged anomalies to a centralized Care Team Dashboard.

2. Core Clinical Guardrails & Safety Policy
Extraction & Routing Only: The AI engine acts strictly as an entity extraction, risk-classification, and triage-routing system. It extracts metrics (e.g., "Fasting Blood Sugar: 245 mg/dL") and flags them against predefined physician targets.
No Autonomous Prescription or Diagnosis: The system never autonomously alters medication dosages, prescribes therapies, or makes diagnostic assertions.
Human-in-the-Loop Dispatch: All outbound clinical nudges, care plan adjustments, and escalations must be reviewed and approved by a care coordinator or clinician via a 1-click dispatch interface.
Instant Emergency Circuit Breaker: Critical anomalies (e.g., severe hypoglycemia under 55 mg/dL or acute red-flag symptoms like chest pain or confusion) immediately trigger standard, non-diagnostic safety instructions to the patient while sounding a P0 priority alarm in the clinical dashboard.

3. High-Level Architecture Overview
The system is decoupled into four primary layers:
Architectural Topology (Component Description)
1. Patient Edge Layer:
Twilio WhatsApp API: Acts as the zero-friction communication interface for patients.
Sarvam AI (Indic Speech & Translation): Transcribes regional voice notes (e.g., Hindi, Marathi, Tamil) and translates them into English for processing, and translates English clinician nudges back into native languages.
Ingress Debounce Buffer (45-second window): Aggregates multi-part patient inputs (such as a glucometer image followed 20 seconds later by an audio explanation) into a single composite payload before triggering AI processing.
2. Multi-Agent Orchestration Layer (LangGraph State Machine):
Agent 1 (Multimodal Extractor): Ingests photos (via Vision LLM) and transcribed voice/text to extract standardized clinical metrics and confidence scores.
Agent 2 (Hybrid Triage & Rules Engine): Evaluates extracted data using deterministic threshold gates and contextual LLM assessment. Routes data to either routine logs or the care team action queue.
Emergency Circuit Breaker: Bypasses manual review queues during critical emergencies to send instant standard safety guidance.
Agent 3 (Proactive EMR Auditor): Runs scheduled batch sweeps over EMR records to identify missing labs, overdue consults, and logging drop-offs.
Agent 4 (Communications Synthesizer): Drafts personalized, empathetic, localized replies and nudges for clinician review.
3. Data Persistence Layer (ABDM / FHIR-Lite Mock EMR):
Built using FastAPI and SQLite, maintaining collections for patients, vitals_logs (FHIR Observations), care_plans (Milestones), and action_queue (Triage Tickets).
4. Care Team Portal (Streamlit Dashboard):
Features a color-coded Unified Triage Inbox, an interactive Patient 360 Glycemic Timeline, and 1-Click Action Dispatchers.

4. Layer Deep-Dive Specifications
Layer A: Patient Edge & Ingress/Egress
Zero-App Ingress: WhatsApp channel managed via Twilio API.
Sarvam AI Integration:
Ingress: Saaras STT + Mayura Translation for regional languages into standardized clinical English.
Egress: Translation of clinician-approved English drafts into the patient's native dialect and script.
Message Debouncing & Aggregation Buffer:
Implements a 45-second sliding window keyed on patient_phone_number to assemble split messages into a single composite payload.
Layer B: Multi-Agent Orchestration (LangGraph State Machine)
Agent 1: Multimodal Extractor (VLM & NLP):
Parses glucometer images, lab slips, and transcribed text.
Extracts: blood_glucose_mg_dl, reading_context (Fasting, Post-Prandial, Random, Bedtime), symptoms list, and confidence_score (0.0 to 1.0).
Validates OCR quality and handles error codes (e.g., E-1, HI, LO, low battery).
Agent 2: Hybrid Triage & Rules Engine:
Deterministic Gate: Directly evaluates extracted vitals against patient targets (e.g., Fasting: 80–130 mg/dL, Post-Prandial: under 180 mg/dL).
Contextual LLM Gate: Evaluates reported symptoms (dizziness, nausea, palpitations, diaphoresis).
Classification Levels:
P0_CRITICAL_EMERGENCY: Blood sugar under 55 mg/dL or over 400 mg/dL with acute distress.
P1_CLINICAL_ESCALATION: Out-of-target reading or persistent mild symptoms.
P2_ROUTINE_LOG: In-range reading, logged directly to EMR without clinician alert.
P3_UNCLEAR_OR_AMBIGUOUS: Extraction confidence under 0.80 or unreadable media; triggers a clarification prompt.
Agent 3: Proactive EMR Auditor:
Runs scheduled sweeps across care_plans and vitals_logs.
Detects:
Overdue HbA1c tests (over 90 days since last recorded test).
Missing doctor follow-up consults.
Logging drop-offs (over 4 days without vital entries for insulin-dependent patients).
Agent 4: Communications Synthesizer:
Generates context-aware, empathetic response drafts matching the patient's language and literacy level.
Uses guardrailed clinical templates (e.g., Rule of 15 guidance, lab booking links).
Layer C: Data Persistence (ABDM / FHIR-Lite Mock EMR)
Backend: FastAPI + SQLite.
Collections:
patients: ABHA ID, demographics, baseline targets, medication regimens, preferred language.
vitals_logs: FHIR Observation equivalent (timestamp, value, unit, modality, source media URI, confidence).
care_plans: FHIR CarePlan milestones (target dates, lab orders, adherence history).
action_queue: Flagged tickets awaiting care coordinator review (priority, extracted data, drafted reply, status).
Layer D: Care Team Portal (Streamlit)
Unified Triage Inbox: Color-coded priority queue (P0 Red, P1 Orange, P3 Yellow) showing patient media, transcript, extracted entities, and drafted reply.
Patient 360 Timeline: Interactive visual history plotting blood sugar against personal target bands, overlaid with medication logs.
1-Click Action Dispatcher: Allows the care team to approve drafts, modify messages, order labs, or schedule tele-consults directly.

5. Core System Workflows (Step-by-Step)
Workflow 1: Multimodal Reactive Ingress & Clinical Triage
Step 1 (Patient Ingress): Patient sends a photo of their glucometer plus a Hindi voice note: "Mera sugar aaj bohot high lag raha hai, aur thodi ghabrahat ho rahi hai."
Step 2 (Transcription & Translation): Sarvam AI transcribes and translates the audio into English: "My sugar feels very high today, and I am feeling a bit anxious/palpitations."
Step 3 (Multimodal Extraction): Extractor Agent parses the glucometer image (reads 245 mg/dL) and extracts the symptom palpitations from the text with a confidence score of 0.94.
Step 4 (Triage Evaluation): Hybrid Triage Engine queries EMR for patient target (80–130 mg/dL). Because 245 > 130 and symptoms are present, it classifies the event as P1_CLINICAL_ESCALATION.
Step 5 (EMR Update & Queueing): Vitals are logged to vitals_logs, and a high-priority ticket is created in action_queue.
Step 6 (Clinician Review & Dispatch): The Care Coordinator reviews the ticket on the Streamlit dashboard, confirms the reading, edits/approves the AI-drafted reply, and clicks "Dispatch".
Step 7 (Localized Delivery): Sarvam AI translates the approved message back into Hindi and dispatches it to the patient via WhatsApp.
Workflow 2: Immediate P0 Emergency Circuit Breaker (Hypoglycemia)
Step 1 (Critical Reading): Patient uploads a photo of a glucometer displaying 48 mg/dL with a text note: "Feeling very shaky."
Step 2 (Emergency Detection): Extractor Agent parses 48 mg/dL. Triage Engine identifies severe hypoglycemia (under 55 mg/dL).
Step 3 (Instant Automated Safety Protocol): The system triggers the Emergency Circuit Breaker, immediately sending standard emergency guidance to the patient's WhatsApp within 3 seconds: "Warning: Your blood sugar is critically low (48 mg/dL). Consume 15 grams of fast-acting sugar (half cup fruit juice or 3 sugar candies) immediately. Rest and recheck in 15 minutes."
Step 4 (Urgent Care Team Alarm): Simultaneously creates a P0_CRITICAL alarm on the Care Team Dashboard with an audible alert and a direct-dial button to call the patient or their emergency contact.
Workflow 3: Proactive Drop-Off & Lab Milestone Auditing
Step 1 (Scheduled Sweep): Proactive Auditor Agent executes a daily sweep of the EMR database.
Step 2 (Milestone Detection): Identifies Patient #1042 whose HbA1c lab order is over 90 days overdue.
Step 3 (Nudge Drafting): Communications Synthesizer drafts a personalized, polite reminder in the patient's preferred language (Marathi) offering a home-collection slot.
Step 4 (Queue Insertion): The nudge is placed in the Care Team "Pending Outreach" queue.
Step 5 (Bulk Approval & Dispatch): The Care Coordinator clicks "Approve All Routine Outreaches", and the nudges are sent to patients via WhatsApp.

6. Core Data Models (Pydantic / FHIR-Lite)
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class PriorityLevel(str, Enum):
  P0_CRITICAL = "P0_CRITICAL"
  P1_ESCALATION = "P1_ESCALATION"
  P2_ROUTINE = "P2_ROUTINE"
  P3_UNCLEAR = "P3_UNCLEAR"


class ReadingContext(str, Enum):
  FASTING = "FASTING"
  POST_PRANDIAL = "POST_PRANDIAL"
  RANDOM = "RANDOM"
  BEDTIME = "BEDTIME"


class ExtractedObservation(BaseModel):
  patient_id: str
  timestamp: datetime = Field(default_factory=datetime.utcnow)
  blood_glucose_mg_dl: Optional[float] = None
  reading_context: ReadingContext = ReadingContext.RANDOM
  symptoms: List[str] = Field(default_factory=list)
  confidence_score: float = Field(ge=0.0, le=1.0)
  raw_transcript: Optional[str] = None
  image_url: Optional[str] = None
  extraction_notes: Optional[str] = None


class PatientProfile(BaseModel):
  patient_id: str
  full_name: str
  phone_number: str
  preferred_language: str = "hi"  # ISO 639-1 (hi, mr, ta, te, en)
  target_fasting_min: float = 80.0
  target_fasting_max: float = 130.0
  target_pp_max: float = 180.0
  last_hba1c_date: Optional[datetime] = None
  last_hba1c_value: Optional[float] = None
  last_log_timestamp: Optional[datetime] = None


class TriageTicket(BaseModel):
  ticket_id: str
  patient_id: str
  priority: PriorityLevel
  extracted_data: ExtractedObservation
  triage_reason: str
  drafted_response: str
  status: str = "PENDING"  # PENDING, APPROVED, REJECTED, RESOLVED
  created_at: datetime = Field(default_factory=datetime.utcnow)


7. Project Directory Structure
glycasync/
├── README.md
├── system_architecture.md
├── requirements.txt
├── .env.example
├── app/
│   ├── main.py                  # FastAPI server for ingress webhooks & REST API
│   ├── config.py                # App settings & LLM/Sarvam API credentials
│   ├── models/                  # Pydantic data schemas
│   │   ├── patient.py
│   │   ├── vitals.py
│   │   └── triage.py
│   ├── db/                      # SQLite persistence & ABDM mock repository
│   │   ├── database.py
│   │   └── seed_data.py         # Mock Indian diabetic patient profiles
│   ├── agents/                  # LangGraph Multi-Agent Workflows
│   │   ├── graph.py             # LangGraph state machine & router
│   │   ├── extractor.py         # VLM & NLP extraction agent
│   │   ├── triage.py            # Hybrid deterministic/LLM triage & circuit breaker
│   │   ├── auditor.py           # Proactive EMR milestone & drop-off auditor
│   │   └── synthesizer.py       # Localized communication synthesizer
│   ├── integrations/            # External edge adapters
│   │   ├── sarvam.py            # Sarvam AI STT & Translation wrapper
│   │   └── twilio_wa.py         # WhatsApp messaging adapter
│   └── simulator/               # Edge testing harness
│       └── mock_ingress.py      # Simulates incoming voice/image WhatsApp payloads
└── ui/
    ├── app.py                   # Streamlit Care Team Dashboard
    ├── components/
    │   ├── triage_inbox.py      # Triage queue with 1-click dispatch
    │   ├── patient_360.py       # Glycemic charts & clinical timeline
    │   └── simulation_panel.py  # Interactive patient input tester
    └── static/                  # Sample test assets (glucometer photos, audio)


8. Phased Implementation Roadmap
Phase
Duration
Scope & Key Deliverables
Phase 1: Foundation & Data Layer
Day 1 (Hours 0–4)
Define Pydantic models & SQLite DB schema. Seed 10 realistic Indian patient personas. Create mock ingress CLI to simulate WhatsApp messages.
Phase 2: Agent Orchestration
Day 1–2 (Hours 4–10)
Build Multimodal Extractor using VLM for glucometer OCR + NLP for symptoms. Build Hybrid Triage engine with deterministic threshold checks. Implement P0 Emergency Circuit Breaker for under 55 mg/dL readings.
Phase 3: Care Team UI & Proactive Auditor
Day 2 (Hours 10–16)
Build Streamlit Dashboard with Unified Triage Inbox and Patient 360 timeline. Implement 1-click Approve/Edit/Dispatch actions. Build Proactive Auditor to detect overdue HbA1c and drop-offs.
Phase 4: Localization & Pitch Polish
Day 2–3 (Hours 16–20)
Integrate Sarvam AI for Hindi/Marathi translation stubs. Run 4 live end-to-end clinical demo scenarios. Package presentation slides and demo video walkthrough.



