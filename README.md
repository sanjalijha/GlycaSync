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

Without Twilio credentials, approved messages are written to the outbound log rather than delivered.

## Connecting WhatsApp

Credentials live in `.env` only — they are never shown in the console. The **WhatsApp** section attaches a live number to a chart and sends a test message.

Outbound needs only credentials. Inbound also needs a public HTTPS address, because Twilio verifies the webhook signature against the exact URL it posted to. Starting the console also starts the inbound listener on port 8000.

1. Put `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_WHATSAPP_FROM` in `.env`. If WhatsApp requires an approved template for the first message, also set `TWILIO_CONTENT_SID`.

2. Every number you want to message must opt in first. From that phone, WhatsApp the sandbox's join code to the sandbox number. WhatsApp does not permit business-initiated messages to numbers that have not opted in, so this is not optional.

3. Expose the API and set `PUBLIC_BASE_URL` to the address:

```bash
uvicorn app.main:app --port 8000
ngrok http 8000                       # copy the https:// address it prints
```

Put that address in `.env` as `PUBLIC_BASE_URL`, then paste `<address>/webhook/whatsapp` into the sandbox's **When a message comes in** field. The two must match exactly or every request is rejected as missigned.

4. Check the wiring and send a test message:

```bash
python -m app.tools.whatsapp_test                 # report configuration
python -m app.tools.whatsapp_test +919821487690   # also send a message
curl localhost:8000/health                        # confirms twilio + signature_check
```

Inbound messages are held for `DEBOUNCE_SECONDS` before processing, so a photo and the voice note that follows it are read as one message rather than two. Attachments are downloaded from Twilio with your credentials into `data/media/` — transcription and photo reading both work off local files, so this step is what makes voice notes and glucometer photos usable at all.

Two things worth knowing. Messages from numbers not in the patient list are recorded and otherwise ignored, never guessed onto a chart. And reading a real glucometer photo needs `LLM_API_KEY` set for a vision model; without it the photo is stored and shown to the clinician, but only the text is parsed.

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
  components/    patient panel, patient record, alert queue, intake, WhatsApp connection
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
