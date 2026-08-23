"""Seed 10 realistic Indian diabetes personas, vitals, care plans, and inbox tickets."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from app.db.database import Repository, get_repo
from app.models.care_plan import CarePlanMilestone, MilestoneStatus, MilestoneType
from app.models.patient import PatientProfile
from app.models.triage import ActionStatus, PriorityLevel, TicketType, TriageTicket
from app.models.vitals import ExtractedObservation, ReadingContext, VitalsLog

UTC = timezone.utc


def _dt(days_ago: float, hour: int = 8, minute: int = 0) -> datetime:
    base = datetime.now(UTC).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return base - timedelta(days=days_ago)


PERSONAS: list[PatientProfile] = [
    PatientProfile(
        patient_id="P-1001",
        full_name="Rajesh Kumar",
        phone_number="+919811000001",
        preferred_language="hi",
        last_hba1c_date=_dt(110, 10),
        last_hba1c_value=8.4,
        last_log_timestamp=_dt(1, 7, 40),
        last_consult_date=_dt(95, 11),
        abha_id="12-3456-7890-1001",
        age=58,
        sex="M",
        city="Delhi",
        diabetes_type="T2DM",
        insulin_dependent=True,
        medications=["Insulin Glargine 12U HS", "Metformin 1000 mg BD", "Telmisartan 40 mg"],
        emergency_contact="Sunita Kumar (wife)",
        emergency_phone="+919811000011",
        literacy_note="conversational",
        notes="Frequent post-breakfast spikes. Lives with family in Mayur Vihar.",
    ),
    PatientProfile(
        patient_id="P-1002",
        full_name="Meera Iyer",
        phone_number="+919443000002",
        preferred_language="ta",
        last_hba1c_date=_dt(40, 9),
        last_hba1c_value=6.8,
        last_log_timestamp=_dt(0, 6, 50),
        last_consult_date=_dt(38, 16),
        abha_id="12-3456-7890-1002",
        age=45,
        sex="F",
        city="Chennai",
        diabetes_type="T2DM",
        insulin_dependent=False,
        medications=["Metformin 500 mg BD", "Glimepiride 1 mg OD"],
        emergency_contact="Karthik Iyer (husband)",
        emergency_phone="+919443000012",
        literacy_note="high",
        notes="Well-controlled. Walks 45 min daily on Marina Beach.",
    ),
    PatientProfile(
        patient_id="P-1003",
        full_name="Abdul Rahman",
        phone_number="+919848000003",
        preferred_language="te",
        last_hba1c_date=_dt(62, 10),
        last_hba1c_value=7.9,
        last_log_timestamp=_dt(6, 21, 10),
        last_consult_date=_dt(70, 12),
        abha_id="12-3456-7890-1003",
        age=62,
        sex="M",
        city="Hyderabad",
        diabetes_type="T2DM",
        insulin_dependent=True,
        medications=["Premix insulin 18-14 U", "Metformin 1000 mg BD"],
        emergency_contact="Ayesha Rahman (daughter)",
        emergency_phone="+919848000013",
        literacy_note="conversational",
        notes="Logging drop-off after grandson's wedding travel.",
    ),
    PatientProfile(
        patient_id="P-1004",
        full_name="Priya Deshmukh",
        phone_number="+919822000004",
        preferred_language="mr",
        last_hba1c_date=_dt(88, 8),
        last_hba1c_value=7.2,
        last_log_timestamp=_dt(2, 8, 5),
        last_consult_date=_dt(120, 15),
        abha_id="12-3456-7890-1004",
        age=38,
        sex="F",
        city="Pune",
        diabetes_type="T2DM",
        insulin_dependent=False,
        medications=["Metformin 500 mg BD"],
        emergency_contact="Amit Deshmukh (husband)",
        emergency_phone="+919822000014",
        literacy_note="high",
        notes="Post-GDM Type 2. Software PM; irregular meals on sprint weeks.",
    ),
    PatientProfile(
        patient_id="P-1005",
        full_name="Suresh Patel",
        phone_number="+919825000005",
        preferred_language="hi",
        last_hba1c_date=_dt(28, 11),
        last_hba1c_value=9.1,
        last_log_timestamp=_dt(0, 19, 20),
        last_consult_date=_dt(25, 10),
        abha_id="12-3456-7890-1005",
        age=71,
        sex="M",
        city="Ahmedabad",
        diabetes_type="T2DM",
        insulin_dependent=True,
        medications=["Insulin Aspart AC", "Insulin Degludec 16U", "Metformin 500 mg"],
        emergency_contact="Nisha Patel (daughter)",
        emergency_phone="+919825000015",
        literacy_note="low",
        notes="CKD stage 2. Family helps with logging. Prefers Gujarati spoken Hindi.",
    ),
    PatientProfile(
        patient_id="P-1006",
        full_name="Fatima Begum",
        phone_number="+919415000006",
        preferred_language="hi",
        last_hba1c_date=_dt(50, 9),
        last_hba1c_value=7.6,
        last_log_timestamp=_dt(1, 22, 0),
        last_consult_date=_dt(140, 14),
        abha_id="12-3456-7890-1006",
        age=55,
        sex="F",
        city="Lucknow",
        diabetes_type="T2DM",
        insulin_dependent=False,
        medications=["Metformin 1000 mg BD", "Sitagliptin 100 mg"],
        emergency_contact="Imran Begum (son)",
        emergency_phone="+919415000016",
        literacy_note="conversational",
        notes="Overdue physician follow-up. Ramadan fasting history — counsel on iftar snacks.",
    ),
    PatientProfile(
        patient_id="P-1007",
        full_name="Ananya Reddy",
        phone_number="+919845000007",
        preferred_language="en",
        last_hba1c_date=_dt(55, 17),
        last_hba1c_value=7.1,
        last_log_timestamp=_dt(0, 7, 10),
        last_consult_date=_dt(50, 17),
        abha_id="12-3456-7890-1007",
        age=29,
        sex="F",
        city="Bengaluru",
        diabetes_type="T1DM",
        insulin_dependent=True,
        medications=["Insulin Aspart (MDI)", "Insulin Glargine 18U"],
        emergency_contact="Rohit Reddy (brother)",
        emergency_phone="+919845000017",
        literacy_note="high",
        notes="Type 1 since age 14. Carb counts. Occasional exercise hypos.",
    ),
    PatientProfile(
        patient_id="P-1008",
        full_name="Harpreet Singh",
        phone_number="+919815000008",
        preferred_language="hi",
        last_hba1c_date=_dt(20, 10),
        last_hba1c_value=10.2,
        last_log_timestamp=_dt(0, 8, 30),
        last_consult_date=_dt(18, 11),
        abha_id="12-3456-7890-1008",
        age=50,
        sex="M",
        city="Amritsar",
        diabetes_type="T2DM",
        insulin_dependent=False,
        medications=["Metformin 1000 mg BD", "Dapagliflozin 10 mg"],
        emergency_contact="Gurpreet Kaur (wife)",
        emergency_phone="+919815000018",
        literacy_note="conversational",
        notes="Newly diagnosed 3 weeks ago. High baseline, education-heavy care plan.",
    ),
    PatientProfile(
        patient_id="P-1009",
        full_name="Lakshmi Nair",
        phone_number="+919447000009",
        preferred_language="en",
        last_hba1c_date=_dt(33, 9),
        last_hba1c_value=6.5,
        last_log_timestamp=_dt(0, 6, 40),
        last_consult_date=_dt(30, 10),
        abha_id="12-3456-7890-1009",
        age=67,
        sex="F",
        city="Kochi",
        diabetes_type="T2DM",
        insulin_dependent=False,
        medications=["Metformin 500 mg OD"],
        emergency_contact="Arun Nair (son)",
        emergency_phone="+919447000019",
        literacy_note="high",
        notes="Excellent adherence. Retired teacher. Prefers English WhatsApp.",
    ),
    PatientProfile(
        patient_id="P-1010",
        full_name="Vikram Joshi",
        phone_number="+919820000010",
        preferred_language="mr",
        last_hba1c_date=_dt(44, 8),
        last_hba1c_value=7.4,
        last_log_timestamp=_dt(0, 21, 45),
        last_consult_date=_dt(42, 18),
        abha_id="12-3456-7890-1010",
        age=42,
        sex="M",
        city="Mumbai",
        diabetes_type="T2DM",
        insulin_dependent=True,
        medications=["Insulin Lispro AC", "Metformin 1000 mg BD"],
        emergency_contact="Neha Joshi (wife)",
        emergency_phone="+919820000020",
        literacy_note="high",
        notes="Long commute, skipped meals, two documented hypos last month.",
    ),
]


def _vital(
    patient_id: str,
    days_ago: float,
    hour: int,
    value: float,
    context: ReadingContext,
    symptoms: list[str] | None = None,
    confidence: float = 0.95,
) -> VitalsLog:
    value = round(value)
    return VitalsLog(
        log_id=f"obs-{patient_id}-{days_ago}-{hour}-{value}".replace(".", ""),
        patient_id=patient_id,
        timestamp=_dt(days_ago, hour, random.randint(0, 40)),
        blood_glucose_mg_dl=value,
        reading_context=context,
        symptoms=symptoms or [],
        confidence_score=confidence,
        modality="whatsapp",
        source="seed",
    )


def _build_vitals() -> list[VitalsLog]:
    rng = random.Random(42)
    logs: list[VitalsLog] = []

    def series(pid: str, days: int, fasting_mu: float, pp_mu: float, noise: float) -> None:
        for d in range(days, 0, -1):
            if rng.random() < 0.18:
                continue
            logs.append(
                _vital(pid, d, 7, max(48, rng.gauss(fasting_mu, noise)), ReadingContext.FASTING)
            )
            if rng.random() > 0.25:
                logs.append(
                    _vital(pid, d, 14, max(70, rng.gauss(pp_mu, noise + 8)), ReadingContext.POST_PRANDIAL)
                )

    series("P-1001", 21, 142, 228, 18)
    series("P-1002", 18, 108, 148, 10)
    series("P-1003", 18, 136, 198, 16)
    # Drop-off: no logs in last 6 days for Rahman — strip recent
    logs = [v for v in logs if not (v.patient_id == "P-1003" and (datetime.now(UTC) - v.timestamp).days < 6)]
    series("P-1004", 16, 118, 168, 12)
    series("P-1005", 20, 168, 246, 22)
    series("P-1006", 14, 126, 176, 12)
    series("P-1007", 16, 112, 164, 20)
    series("P-1008", 12, 188, 262, 24)
    series("P-1009", 20, 102, 138, 8)
    series("P-1010", 16, 121, 172, 18)

    logs.append(
        _vital("P-1010", 12, 16, 52, ReadingContext.RANDOM, ["shakiness", "sweating"], 0.97)
    )
    # Today's critical low, so a fresh install shows the circuit breaker in its resting state.
    logs.append(
        _vital("P-1010", 0, 7, 46, ReadingContext.FASTING, ["shakiness", "sweating"], 0.96)
    )
    logs.append(
        _vital("P-1001", 4, 9, 268, ReadingContext.POST_PRANDIAL, ["fatigue"], 0.93)
    )
    return logs


def _build_care_plans() -> list[CarePlanMilestone]:
    plans: list[CarePlanMilestone] = []

    def add(
        pid: str,
        mtype: MilestoneType,
        title: str,
        days_offset: int,
        status: MilestoneStatus,
        notes: str = "",
        completed_offset: int | None = None,
    ) -> None:
        target = _dt(abs(days_offset) if days_offset > 0 else 0, 10) + (
            timedelta(days=0) if days_offset > 0 else timedelta(days=abs(days_offset))
        )
        if days_offset > 0:
            target = _dt(days_offset, 10)
        else:
            target = datetime.now(UTC) + timedelta(days=abs(days_offset))
        completed = _dt(completed_offset, 10) if completed_offset is not None else None
        plans.append(
            CarePlanMilestone(
                plan_id=f"cp-{pid}-{mtype.value}-{abs(days_offset)}",
                patient_id=pid,
                milestone_type=mtype,
                title=title,
                target_date=target,
                completed_date=completed,
                status=status,
                notes=notes,
            )
        )

    add("P-1001", MilestoneType.HBA1C, "Quarterly HbA1c", 20, MilestoneStatus.OVERDUE, "Last 8.4% — due 90+ days")
    add("P-1001", MilestoneType.CONSULT, "Endocrinology follow-up", 5, MilestoneStatus.OVERDUE)
    add("P-1001", MilestoneType.RETINAL, "Retinal screening", -20, MilestoneStatus.SCHEDULED)
    add("P-1002", MilestoneType.HBA1C, "HbA1c", 40, MilestoneStatus.COMPLETED, completed_offset=40)
    add("P-1002", MilestoneType.FOOT_EXAM, "Annual foot exam", -40, MilestoneStatus.SCHEDULED)
    add("P-1003", MilestoneType.HBA1C, "Quarterly HbA1c", -28, MilestoneStatus.SCHEDULED)
    add("P-1003", MilestoneType.CONSULT, "Insulin review", 10, MilestoneStatus.OVERDUE)
    add("P-1004", MilestoneType.CONSULT, "Physician follow-up", 30, MilestoneStatus.OVERDUE, "Last visit ~4 months ago")
    add("P-1004", MilestoneType.HBA1C, "HbA1c", -2, MilestoneStatus.SCHEDULED)
    add("P-1005", MilestoneType.HBA1C, "HbA1c", 28, MilestoneStatus.COMPLETED, completed_offset=28)
    add("P-1005", MilestoneType.LIPID, "Lipid panel", -14, MilestoneStatus.SCHEDULED)
    add("P-1006", MilestoneType.CONSULT, "OPD follow-up", 50, MilestoneStatus.OVERDUE)
    add("P-1007", MilestoneType.HBA1C, "HbA1c", -35, MilestoneStatus.SCHEDULED)
    add("P-1008", MilestoneType.CONSULT, "New-onset education visit", -6, MilestoneStatus.SCHEDULED)
    add("P-1009", MilestoneType.HBA1C, "HbA1c", 33, MilestoneStatus.COMPLETED, completed_offset=33)
    add("P-1010", MilestoneType.HBA1C, "HbA1c", -46, MilestoneStatus.SCHEDULED)
    add("P-1010", MilestoneType.FOOT_EXAM, "Foot exam", -10, MilestoneStatus.SCHEDULED)
    return plans


def _seed_inbox(repo: Repository) -> None:
    if repo.list_tickets():
        return

    vikram = ExtractedObservation(
        patient_id="P-1010",
        timestamp=_dt(0, 7, 4),
        blood_glucose_mg_dl=46,
        reading_context=ReadingContext.FASTING,
        symptoms=["shakiness", "sweating"],
        confidence_score=0.96,
        raw_transcript="Sugar 46 aaya hai, haath kaanp rahe hain aur pasina aa raha hai.",
        translated_text="Sugar came to 46, my hands are shaking and I am sweating.",
        modality="text",
        extraction_notes="Severe hypoglycemia with adrenergic symptoms.",
    )
    repo.insert_ticket(
        TriageTicket(
            ticket_id="T-SEED-P0-1010",
            patient_id="P-1010",
            priority=PriorityLevel.P0_CRITICAL,
            extracted_data=vikram,
            triage_reason="Severe hypoglycemia 46 mg/dL (threshold < 55).",
            drafted_response=(
                "Vikram ji, a coordinator is calling you now. Stay seated, keep someone with you, "
                "and recheck your sugar 15 minutes after taking the juice or sugar."
            ),
            drafted_response_localized=(
                "नमस्कार — Vikram ji, a coordinator is calling you now. Stay seated, keep someone "
                "with you, and recheck your sugar 15 minutes after taking the juice or sugar.\n"
                "— GlycaSync देखभाल टीम"
            ),
            dispatched_message=(
                "Warning: Your blood sugar is critically low (46 mg/dL). Consume 15 grams of "
                "fast-acting sugar (half cup fruit juice or 3 sugar candies) immediately. Rest and "
                "recheck in 15 minutes. If you feel confused, faint, or cannot swallow, ask someone "
                "nearby to help and call emergency services (108)."
            ),
            status=ActionStatus.AUTO_DISPATCHED,
            ticket_type=TicketType.EMERGENCY,
        )
    )

    rajesh = ExtractedObservation(
        patient_id="P-1001",
        timestamp=_dt(0, 8, 12),
        blood_glucose_mg_dl=245,
        reading_context=ReadingContext.POST_PRANDIAL,
        symptoms=["palpitations"],
        confidence_score=0.94,
        raw_transcript="Mera sugar aaj bohot high lag raha hai, aur thodi ghabrahat ho rahi hai.",
        translated_text="My sugar feels very high today, and I am feeling a bit anxious/palpitations.",
        image_url="ui/static/glucometer_245.png",
        modality="multimodal",
        extraction_notes="Glucometer OCR 245 mg/dL; Hindi voice note translated.",
    )
    repo.insert_ticket(
        TriageTicket(
            ticket_id="T-SEED-P1-1001",
            patient_id="P-1001",
            priority=PriorityLevel.P1_ESCALATION,
            extracted_data=rajesh,
            triage_reason="Post-prandial 245 mg/dL exceeds personal target (≤180) with palpitations.",
            drafted_response=(
                "Namaste Rajesh ji — we received your 245 mg/dL reading after meals along with "
                "palpitations. This is above your target. Please sit, sip water, and avoid extra "
                "insulin unless your care team confirms. A coordinator will call you shortly."
            ),
            drafted_response_localized=(
                "नमस्ते राजेश जी — आपका खाने के बाद शुगर 245 mg/dL और घबराहट दर्ज हुई है। "
                "यह आपके लक्ष्य से ऊपर है। आराम करें, पानी पिएँ। टीम जल्द कॉल करेगी।"
            ),
            status=ActionStatus.PENDING,
            ticket_type=TicketType.INGRESS,
        )
    )

    unclear = ExtractedObservation(
        patient_id="P-1005",
        timestamp=_dt(0, 19, 5),
        blood_glucose_mg_dl=None,
        reading_context=ReadingContext.RANDOM,
        symptoms=[],
        confidence_score=0.31,
        raw_transcript="machine pe kuch error aa raha hai",
        translated_text="There is some error showing on the machine.",
        image_url="ui/static/glucometer_error.png",
        device_error="E-1",
        modality="image",
        extraction_notes="Unreadable strip / E-1 error code. Clarification required.",
    )
    repo.insert_ticket(
        TriageTicket(
            ticket_id="T-SEED-P3-1005",
            patient_id="P-1005",
            priority=PriorityLevel.P3_UNCLEAR,
            extracted_data=unclear,
            triage_reason="Extraction confidence 0.31 with device error E-1. Cannot log a numeric reading.",
            drafted_response=(
                "Suresh ji, the glucometer photo looks like an E-1 strip error. Please use a new "
                "strip, ensure your hands are clean and dry, and send a fresh photo of the number screen."
            ),
            drafted_response_localized=(
                "सुरेश जी, फोटो में मशीन E-1 एरर दिखा रही है। नया स्ट्रिप लगाकर साफ सूखे हाथों से "
                "दोबारा जाँच करें और नंबर वाली स्क्रीन की फोटो भेजें।"
            ),
            status=ActionStatus.PENDING,
            ticket_type=TicketType.INGRESS,
        )
    )

    outreach_obs = ExtractedObservation(
        patient_id="P-1001",
        timestamp=datetime.now(UTC),
        confidence_score=1.0,
        extraction_notes="Proactive EMR auditor — HbA1c overdue 110 days.",
        modality="system",
    )
    repo.insert_ticket(
        TriageTicket(
            ticket_id="T-SEED-OUT-1001",
            patient_id="P-1001",
            priority=PriorityLevel.P1_ESCALATION,
            extracted_data=outreach_obs,
            triage_reason="HbA1c last recorded 110 days ago (8.4%). ADA/RSSDI cadence is ~90 days.",
            drafted_response=(
                "Rajesh ji, your HbA1c test is now overdue. We can arrange a home sample collection "
                "tomorrow morning between 7–9 am. Reply YES to confirm the slot."
            ),
            drafted_response_localized=(
                "राजेश जी, आपकी HbA1c जाँच overdue हो गई है। कल सुबह 7–9 बजे घर से सैंपल "
                "ले सकते हैं। स्लॉट कन्फर्म करने के लिए YES लिखें।"
            ),
            status=ActionStatus.PENDING,
            ticket_type=TicketType.OUTREACH,
        )
    )

    drop_obs = ExtractedObservation(
        patient_id="P-1003",
        timestamp=datetime.now(UTC),
        confidence_score=1.0,
        extraction_notes="Proactive EMR auditor — insulin-dependent logging drop-off.",
        modality="system",
    )
    repo.insert_ticket(
        TriageTicket(
            ticket_id="T-SEED-OUT-1003",
            patient_id="P-1003",
            priority=PriorityLevel.P1_ESCALATION,
            extracted_data=drop_obs,
            triage_reason="No glucose logs for 6 days. Patient is insulin-dependent (drop-off threshold: 4 days).",
            drafted_response=(
                "Abdul Rahman ji, we have not received your sugar readings for 6 days. "
                "A quick fasting photo tomorrow morning helps us keep your insulin plan safe. "
                "Need help using the glucometer? Reply HELP."
            ),
            drafted_response_localized=(
                "అబ్దుల్ రహ్మాన్ గారు, 6 రోజులుగా షుగర్ రీడింగ్స్ రాలేదు. రేపు ఉదయం "
                "ఫాస్టింగ్ ఫోటో పంపండి. మీకు సహాయం కావాలంటే HELP అని రాయండి."
            ),
            status=ActionStatus.PENDING,
            ticket_type=TicketType.OUTREACH,
        )
    )


def seed(repo: Repository | None = None, force: bool = False) -> dict[str, int]:
    repo = repo or get_repo()
    if repo.patient_count():
        if not force:
            return {"patients": repo.patient_count(), "skipped": 1}
        repo.clear()

    for persona in PERSONAS:
        repo.upsert_patient(persona)
    for vital in _build_vitals():
        repo.insert_vital(vital)
    # Re-apply last_log from personas after vitals (Rahman drop-off must stay 6d)
    for persona in PERSONAS:
        if persona.last_log_timestamp:
            repo.update_patient_last_log(persona.patient_id, persona.last_log_timestamp)
    for plan in _build_care_plans():
        repo.upsert_care_plan(plan)
    _seed_inbox(repo)
    return {
        "patients": repo.patient_count(),
        "vitals": sum(len(repo.list_vitals(p.patient_id)) for p in PERSONAS),
        "care_plans": len(repo.list_care_plans()),
        "tickets": len(repo.list_tickets()),
    }


def ensure_seeded() -> None:
    repo = get_repo()
    if repo.patient_count() == 0:
        seed(repo)


if __name__ == "__main__":
    stats = seed(force=True)
    print("Seeded GlycaSync EMR:", stats)
