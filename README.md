# GlycaSync

Assistive diabetes care coordination for Indian clinics. GlycaSync watches the gap between visits from two directions: it reads what patients send in on WhatsApp, and it reviews the record for care that has fallen behind.

It does not diagnose, prescribe, or change insulin doses. It extracts readings, classifies risk, and routes work to a clinician. Every outbound message is approved by a human, with one exception: a critically low reading triggers standard first-aid guidance immediately.

## What it does

**Inbound.** A patient sends a glucometer photo and a voice note in Hindi. Speech is transcribed and translated, the reading and symptoms are extracted with a confidence score, and the result is triaged against that patient's own targets. In-range readings are filed to the chart. Anything out of range, symptomatic, or unreadable becomes an alert with a drafted reply waiting for approval.

**Outbound.** A scheduled review sweeps every record for HbA1c tests over 90 days old, missed follow-ups, and insulin-dependent patients who have stopped logging for four days. Each finding becomes a drafted outreach message in the same inbox.

**Critical lows.** Under 55 mg/dL, or a red-flag symptom such as chest pain or confusion, sends the patient standard safety guidance within seconds and raises an immediate alert for the care team with one-tap dialling.

## Running it

Requires Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optional; runs without credentials

python -m app.db.seed_data    # loads a demo panel of 10 patients
streamlit run ui/app.py
```

The API and WhatsApp webhook run separately:

```bash
uvicorn app.main:app --reload --port 8000
```

## Tests

```bash
pytest
```

The suite covers triage thresholds and safety guardrails, entity extraction across English and transliterated Indic text, the record repository, the scheduled review, the ingress pipeline end to end, message debouncing, and the REST API.

## Configuration

Everything runs offline with rule-based fallbacks. Fill in `.env` to switch on live services:

| Variable | Effect |
|---|---|
| `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` | Uses an OpenAI-compatible model for extraction and photo reading instead of the rule-based parser |
| `SARVAM_API_KEY` | Live Indic speech-to-text and translation |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` | Delivers approved messages over WhatsApp |

Without Twilio credentials, approved messages are written to the outbound log rather than delivered. Point your Twilio WhatsApp sender's inbound webhook at `POST /webhook/whatsapp`.

## Layout

```
app/
  agents/        extraction, triage, scheduled review, message drafting
  db/            SQLite record store and demo panel
  integrations/  Sarvam speech and translation, Twilio WhatsApp, message debouncing
  analytics.py   derived metrics: time in range, control status, quiet patients
  main.py        REST API and WhatsApp webhook
ui/
  app.py         care team console
  design.py      design tokens and stylesheet
  glyphs.py      the corridor trace
  components/    patient panel, patient record, alert queue, intake tools
tests/
```

## The console

The console is organised around the **corridor** — each patient's own target range,
which is what every reading is judged against. Colour is reserved for that judgement:
a value is below, inside, or above its corridor, and nothing decorative is coloured.

Every patient in the panel carries a **corridor trace**, a sparkline of their recent
readings drawn over their target band, so a clinician can scan the panel by shape
before reading a single number. A flat line inside the band is a patient holding their
range; spikes above it, or dips below the hypo rule, stand out immediately.

Design notes and the clinical rationale are in [`system_architecture.md`](system_architecture.md).
