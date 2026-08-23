from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from app.config import get_settings
from app.models.care_plan import CarePlanMilestone, MilestoneStatus, MilestoneType
from app.models.patient import PatientProfile
from app.models.triage import ActionStatus, PriorityLevel, TicketType, TriageTicket
from app.models.vitals import ExtractedObservation, ReadingContext, VitalsLog, utcnow

# Indian mobile numbers are 10 digits after the +91 country code.
SUBSCRIBER_DIGITS = 10

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    phone_number TEXT NOT NULL UNIQUE,
    preferred_language TEXT NOT NULL DEFAULT 'hi',
    target_fasting_min REAL NOT NULL DEFAULT 80,
    target_fasting_max REAL NOT NULL DEFAULT 130,
    target_pp_max REAL NOT NULL DEFAULT 180,
    last_hba1c_date TEXT,
    last_hba1c_value REAL,
    last_log_timestamp TEXT,
    last_consult_date TEXT,
    abha_id TEXT,
    age INTEGER,
    sex TEXT,
    city TEXT,
    diabetes_type TEXT,
    insulin_dependent INTEGER NOT NULL DEFAULT 0,
    medications TEXT NOT NULL DEFAULT '[]',
    emergency_contact TEXT,
    emergency_phone TEXT,
    literacy_note TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS vitals_logs (
    log_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    blood_glucose_mg_dl REAL,
    reading_context TEXT NOT NULL,
    symptoms TEXT NOT NULL DEFAULT '[]',
    confidence_score REAL NOT NULL DEFAULT 0,
    raw_transcript TEXT,
    translated_text TEXT,
    image_url TEXT,
    extraction_notes TEXT,
    device_error TEXT,
    modality TEXT NOT NULL DEFAULT 'text',
    unit TEXT NOT NULL DEFAULT 'mg/dL',
    source TEXT NOT NULL DEFAULT 'whatsapp',
    resource_type TEXT NOT NULL DEFAULT 'Observation',
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

CREATE TABLE IF NOT EXISTS care_plans (
    plan_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    milestone_type TEXT NOT NULL,
    title TEXT NOT NULL,
    target_date TEXT NOT NULL,
    completed_date TEXT,
    status TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

CREATE TABLE IF NOT EXISTS action_queue (
    ticket_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    priority TEXT NOT NULL,
    extracted_data TEXT NOT NULL,
    triage_reason TEXT NOT NULL,
    drafted_response TEXT NOT NULL,
    drafted_response_localized TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    ticket_type TEXT NOT NULL DEFAULT 'INGRESS',
    created_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewed_by TEXT,
    dispatched_message TEXT,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    patient_id TEXT,
    phone_number TEXT,
    direction TEXT NOT NULL,
    content TEXT NOT NULL,
    language TEXT,
    media_url TEXT,
    ticket_id TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vitals_patient_ts ON vitals_logs(patient_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON action_queue(status, priority, created_at);
CREATE INDEX IF NOT EXISTS idx_care_patient ON care_plans(patient_id, status);
"""


def _iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.isoformat()
    return value.isoformat()


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value)


class Repository:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        settings = get_settings()
        self.db_path = Path(db_path) if db_path else settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def clear(self) -> None:
        """Empty every table, keeping the schema. Used to reseed a demo database."""
        with self.connect() as conn:
            for table in ("messages", "action_queue", "care_plans", "vitals_logs", "patients"):
                conn.execute(f"DELETE FROM {table}")

    def patient_count(self) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM patients").fetchone()
        return int(row["n"])

    def upsert_patient(self, patient: PatientProfile) -> None:
        payload = (
            patient.patient_id,
            patient.full_name,
            patient.phone_number,
            patient.preferred_language,
            patient.target_fasting_min,
            patient.target_fasting_max,
            patient.target_pp_max,
            _iso(patient.last_hba1c_date),
            patient.last_hba1c_value,
            _iso(patient.last_log_timestamp),
            _iso(patient.last_consult_date),
            patient.abha_id,
            patient.age,
            patient.sex,
            patient.city,
            patient.diabetes_type,
            1 if patient.insulin_dependent else 0,
            json.dumps(patient.medications),
            patient.emergency_contact,
            patient.emergency_phone,
            patient.literacy_note,
            patient.notes,
        )
        sql = """
        INSERT INTO patients (
            patient_id, full_name, phone_number, preferred_language,
            target_fasting_min, target_fasting_max, target_pp_max,
            last_hba1c_date, last_hba1c_value, last_log_timestamp, last_consult_date,
            abha_id, age, sex, city, diabetes_type, insulin_dependent,
            medications, emergency_contact, emergency_phone, literacy_note, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(patient_id) DO UPDATE SET
            full_name=excluded.full_name,
            phone_number=excluded.phone_number,
            preferred_language=excluded.preferred_language,
            target_fasting_min=excluded.target_fasting_min,
            target_fasting_max=excluded.target_fasting_max,
            target_pp_max=excluded.target_pp_max,
            last_hba1c_date=excluded.last_hba1c_date,
            last_hba1c_value=excluded.last_hba1c_value,
            last_log_timestamp=excluded.last_log_timestamp,
            last_consult_date=excluded.last_consult_date,
            abha_id=excluded.abha_id,
            age=excluded.age,
            sex=excluded.sex,
            city=excluded.city,
            diabetes_type=excluded.diabetes_type,
            insulin_dependent=excluded.insulin_dependent,
            medications=excluded.medications,
            emergency_contact=excluded.emergency_contact,
            emergency_phone=excluded.emergency_phone,
            literacy_note=excluded.literacy_note,
            notes=excluded.notes
        """
        with self.connect() as conn:
            conn.execute(sql, payload)

    def _row_to_patient(self, row: sqlite3.Row) -> PatientProfile:
        return PatientProfile(
            patient_id=row["patient_id"],
            full_name=row["full_name"],
            phone_number=row["phone_number"],
            preferred_language=row["preferred_language"],
            target_fasting_min=row["target_fasting_min"],
            target_fasting_max=row["target_fasting_max"],
            target_pp_max=row["target_pp_max"],
            last_hba1c_date=_parse_dt(row["last_hba1c_date"]),
            last_hba1c_value=row["last_hba1c_value"],
            last_log_timestamp=_parse_dt(row["last_log_timestamp"]),
            last_consult_date=_parse_dt(row["last_consult_date"]),
            abha_id=row["abha_id"],
            age=row["age"] or 50,
            sex=row["sex"] or "M",
            city=row["city"] or "Mumbai",
            diabetes_type=row["diabetes_type"] or "T2DM",
            insulin_dependent=bool(row["insulin_dependent"]),
            medications=json.loads(row["medications"] or "[]"),
            emergency_contact=row["emergency_contact"] or "",
            emergency_phone=row["emergency_phone"] or "",
            literacy_note=row["literacy_note"] or "standard",
            notes=row["notes"] or "",
        )

    def list_patients(self) -> list[PatientProfile]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM patients ORDER BY full_name"
            ).fetchall()
        return [self._row_to_patient(r) for r in rows]

    def get_patient(self, patient_id: str) -> Optional[PatientProfile]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM patients WHERE patient_id = ?", (patient_id,)
            ).fetchone()
        return self._row_to_patient(row) if row else None

    def get_patient_by_phone(self, phone_number: str) -> Optional[PatientProfile]:
        """Resolve a patient from an inbound number.

        Matches on the national subscriber number (last 10 digits) so that country
        codes and formatting do not matter. Anything shorter is rejected outright —
        a partial number must never resolve to the wrong patient's chart.
        """
        digits = "".join(ch for ch in phone_number if ch.isdigit())
        if len(digits) < SUBSCRIBER_DIGITS:
            return None
        needle = digits[-SUBSCRIBER_DIGITS:]
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM patients").fetchall()
        for row in rows:
            stored = "".join(ch for ch in row["phone_number"] if ch.isdigit())
            if len(stored) >= SUBSCRIBER_DIGITS and stored[-SUBSCRIBER_DIGITS:] == needle:
                return self._row_to_patient(row)
        return None

    def update_patient_last_log(self, patient_id: str, ts: Optional[datetime] = None) -> None:
        stamp = _iso(ts or utcnow())
        with self.connect() as conn:
            conn.execute(
                "UPDATE patients SET last_log_timestamp = ? WHERE patient_id = ?",
                (stamp, patient_id),
            )

    def insert_vital(self, log: VitalsLog) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO vitals_logs (
                    log_id, patient_id, timestamp, blood_glucose_mg_dl, reading_context,
                    symptoms, confidence_score, raw_transcript, translated_text, image_url,
                    extraction_notes, device_error, modality, unit, source, resource_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log.log_id,
                    log.patient_id,
                    _iso(log.timestamp),
                    log.blood_glucose_mg_dl,
                    log.reading_context.value,
                    json.dumps(log.symptoms),
                    log.confidence_score,
                    log.raw_transcript,
                    log.translated_text,
                    log.image_url,
                    log.extraction_notes,
                    log.device_error,
                    log.modality,
                    log.unit,
                    log.source,
                    log.resource_type,
                ),
            )
        if log.blood_glucose_mg_dl is not None:
            self.update_patient_last_log(log.patient_id, log.timestamp)

    def list_vitals(self, patient_id: str, limit: int = 200) -> list[VitalsLog]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM vitals_logs
                WHERE patient_id = ?
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (patient_id, limit),
            ).fetchall()
        return [self._row_to_vital(r) for r in rows]

    def _row_to_vital(self, row: sqlite3.Row) -> VitalsLog:
        return VitalsLog(
            log_id=row["log_id"],
            patient_id=row["patient_id"],
            timestamp=_parse_dt(row["timestamp"]) or utcnow(),
            blood_glucose_mg_dl=row["blood_glucose_mg_dl"],
            reading_context=ReadingContext(row["reading_context"]),
            symptoms=json.loads(row["symptoms"] or "[]"),
            confidence_score=row["confidence_score"] or 0.0,
            raw_transcript=row["raw_transcript"],
            translated_text=row["translated_text"],
            image_url=row["image_url"],
            extraction_notes=row["extraction_notes"],
            device_error=row["device_error"],
            modality=row["modality"] or "text",
            unit=row["unit"] or "mg/dL",
            source=row["source"] or "whatsapp",
            resource_type=row["resource_type"] or "Observation",
        )

    def upsert_care_plan(self, plan: CarePlanMilestone) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO care_plans (
                    plan_id, patient_id, milestone_type, title, target_date,
                    completed_date, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(plan_id) DO UPDATE SET
                    status=excluded.status,
                    completed_date=excluded.completed_date,
                    notes=excluded.notes,
                    target_date=excluded.target_date
                """,
                (
                    plan.plan_id,
                    plan.patient_id,
                    plan.milestone_type.value,
                    plan.title,
                    _iso(plan.target_date),
                    _iso(plan.completed_date),
                    plan.status.value,
                    plan.notes,
                ),
            )

    def list_care_plans(self, patient_id: Optional[str] = None) -> list[CarePlanMilestone]:
        sql = "SELECT * FROM care_plans"
        args: tuple[Any, ...] = ()
        if patient_id:
            sql += " WHERE patient_id = ?"
            args = (patient_id,)
        sql += " ORDER BY target_date ASC"
        with self.connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [
            CarePlanMilestone(
                plan_id=r["plan_id"],
                patient_id=r["patient_id"],
                milestone_type=MilestoneType(r["milestone_type"]),
                title=r["title"],
                target_date=_parse_dt(r["target_date"]) or utcnow(),
                completed_date=_parse_dt(r["completed_date"]),
                status=MilestoneStatus(r["status"]),
                notes=r["notes"] or "",
            )
            for r in rows
        ]

    def insert_ticket(self, ticket: TriageTicket) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO action_queue (
                    ticket_id, patient_id, priority, extracted_data, triage_reason,
                    drafted_response, drafted_response_localized, status, ticket_type,
                    created_at, reviewed_at, reviewed_by, dispatched_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket.ticket_id,
                    ticket.patient_id,
                    ticket.priority.value,
                    ticket.extracted_data.model_dump_json(),
                    ticket.triage_reason,
                    ticket.drafted_response,
                    ticket.drafted_response_localized,
                    ticket.status.value,
                    ticket.ticket_type.value,
                    _iso(ticket.created_at),
                    _iso(ticket.reviewed_at),
                    ticket.reviewed_by,
                    ticket.dispatched_message,
                ),
            )

    def get_ticket(self, ticket_id: str) -> Optional[TriageTicket]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM action_queue WHERE ticket_id = ?", (ticket_id,)
            ).fetchone()
        return self._row_to_ticket(row) if row else None

    def list_tickets(
        self,
        status: Optional[str] = None,
        ticket_type: Optional[str] = None,
    ) -> list[TriageTicket]:
        clauses: list[str] = []
        args: list[Any] = []
        if status:
            clauses.append("status = ?")
            args.append(status)
        if ticket_type:
            clauses.append("ticket_type = ?")
            args.append(ticket_type)
        sql = "SELECT * FROM action_queue"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += """
            ORDER BY CASE priority
                WHEN 'P0_CRITICAL' THEN 0
                WHEN 'P1_ESCALATION' THEN 1
                WHEN 'P3_UNCLEAR' THEN 2
                ELSE 3
            END, created_at DESC
        """
        with self.connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [self._row_to_ticket(r) for r in rows]

    def update_ticket(
        self,
        ticket_id: str,
        *,
        status: Optional[ActionStatus] = None,
        drafted_response: Optional[str] = None,
        drafted_response_localized: Optional[str] = None,
        reviewed_by: Optional[str] = None,
        dispatched_message: Optional[str] = None,
    ) -> Optional[TriageTicket]:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None
        if status:
            ticket.status = status
            ticket.reviewed_at = utcnow()
        if drafted_response is not None:
            ticket.drafted_response = drafted_response
        if drafted_response_localized is not None:
            ticket.drafted_response_localized = drafted_response_localized
        if reviewed_by is not None:
            ticket.reviewed_by = reviewed_by
        if dispatched_message is not None:
            ticket.dispatched_message = dispatched_message
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE action_queue SET
                    status = ?, drafted_response = ?, drafted_response_localized = ?,
                    reviewed_at = ?, reviewed_by = ?, dispatched_message = ?
                WHERE ticket_id = ?
                """,
                (
                    ticket.status.value,
                    ticket.drafted_response,
                    ticket.drafted_response_localized,
                    _iso(ticket.reviewed_at),
                    ticket.reviewed_by,
                    ticket.dispatched_message,
                    ticket.ticket_id,
                ),
            )
        return ticket

    def _row_to_ticket(self, row: sqlite3.Row) -> TriageTicket:
        extracted = ExtractedObservation.model_validate_json(row["extracted_data"])
        return TriageTicket(
            ticket_id=row["ticket_id"],
            patient_id=row["patient_id"],
            priority=PriorityLevel(row["priority"]),
            extracted_data=extracted,
            triage_reason=row["triage_reason"],
            drafted_response=row["drafted_response"],
            drafted_response_localized=row["drafted_response_localized"] or "",
            status=ActionStatus(row["status"]),
            ticket_type=TicketType(row["ticket_type"]),
            created_at=_parse_dt(row["created_at"]) or utcnow(),
            reviewed_at=_parse_dt(row["reviewed_at"]),
            reviewed_by=row["reviewed_by"],
            dispatched_message=row["dispatched_message"],
        )

    def insert_message(
        self,
        message_id: str,
        *,
        patient_id: Optional[str],
        phone_number: Optional[str],
        direction: str,
        content: str,
        language: str = "en",
        media_url: Optional[str] = None,
        ticket_id: Optional[str] = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (
                    message_id, patient_id, phone_number, direction, content,
                    language, media_url, ticket_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    patient_id,
                    phone_number,
                    direction,
                    content,
                    language,
                    media_url,
                    ticket_id,
                    _iso(utcnow()),
                ),
            )

    def list_messages(self, patient_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE patient_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (patient_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def recent_messages(self, limit: int = 20, direction: Optional[str] = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM messages"
        args: list[Any] = []
        if direction:
            sql += " WHERE direction = ?"
            args.append(direction)
        sql += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        with self.connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    def dashboard_counts(self) -> dict[str, int]:
        with self.connect() as conn:
            open_p0 = conn.execute(
                "SELECT COUNT(*) AS n FROM action_queue WHERE status IN ('PENDING','AUTO_DISPATCHED') AND priority='P0_CRITICAL'"
            ).fetchone()["n"]
            open_p1 = conn.execute(
                "SELECT COUNT(*) AS n FROM action_queue WHERE status='PENDING' AND priority='P1_ESCALATION'"
            ).fetchone()["n"]
            open_p3 = conn.execute(
                "SELECT COUNT(*) AS n FROM action_queue WHERE status='PENDING' AND priority='P3_UNCLEAR'"
            ).fetchone()["n"]
            outreach = conn.execute(
                "SELECT COUNT(*) AS n FROM action_queue WHERE status='PENDING' AND ticket_type='OUTREACH'"
            ).fetchone()["n"]
            patients = conn.execute("SELECT COUNT(*) AS n FROM patients").fetchone()["n"]
        return {
            "p0": int(open_p0),
            "p1": int(open_p1),
            "p3": int(open_p3),
            "outreach": int(outreach),
            "patients": int(patients),
        }


@lru_cache
def get_repo() -> Repository:
    return Repository()
