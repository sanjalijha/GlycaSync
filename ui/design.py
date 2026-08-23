"""Design tokens and stylesheet for the care team console.

The thesis: colour in this interface always means something about a patient's
glucose. Chrome, navigation and controls are monochrome; the clinical palette is
reserved for readings relative to a patient's own target corridor. Nothing
decorative is coloured.
"""

from __future__ import annotations

from app.analytics import CONTROL_ACTION, CONTROL_GOOD, CONTROL_SILENT, CONTROL_WATCH
from app.models.triage import PriorityLevel

# Chrome — monochrome
INK = "#10151f"
GRAPHITE = "#3a4453"
SLATE = "#5f6b7c"
MUTED = "#8a94a2"
LINE = "#e2e6ec"
HAIRLINE = "#eef1f5"
PAPER = "#f6f7f9"
SURFACE = "#ffffff"
FOCUS = "#1f6feb"

# Clinical — a reading relative to its corridor
BELOW = "#c2401f"
INSIDE = "#4e8c6a"
ABOVE = "#c08422"
QUIET = "#8a94a2"

BELOW_WASH = "#fbeeea"
INSIDE_WASH = "#eef5f1"
ABOVE_WASH = "#fbf4e7"
QUIET_WASH = "#f2f4f7"

STATUS_TONE = {
    CONTROL_ACTION: BELOW,
    CONTROL_WATCH: ABOVE,
    CONTROL_SILENT: QUIET,
    CONTROL_GOOD: INSIDE,
}

STATUS_WASH = {
    CONTROL_ACTION: BELOW_WASH,
    CONTROL_WATCH: ABOVE_WASH,
    CONTROL_SILENT: QUIET_WASH,
    CONTROL_GOOD: INSIDE_WASH,
}

STATUS_NOTE = {
    CONTROL_ACTION: "Outside corridor or flagged",
    CONTROL_WATCH: "Drifting out of corridor",
    CONTROL_SILENT: "No reading in 7 days",
    CONTROL_GOOD: "Holding inside corridor",
}

PRIORITY_LABEL = {
    PriorityLevel.P0_CRITICAL: "Critical",
    PriorityLevel.P1_ESCALATION: "Escalation",
    PriorityLevel.P3_UNCLEAR: "Unclear",
    PriorityLevel.P2_ROUTINE: "Routine",
}

PRIORITY_TONE = {
    PriorityLevel.P0_CRITICAL: BELOW,
    PriorityLevel.P1_ESCALATION: ABOVE,
    PriorityLevel.P3_UNCLEAR: SLATE,
    PriorityLevel.P2_ROUTINE: INSIDE,
}

PRIORITY_WASH = {
    PriorityLevel.P0_CRITICAL: BELOW_WASH,
    PriorityLevel.P1_ESCALATION: ABOVE_WASH,
    PriorityLevel.P3_UNCLEAR: QUIET_WASH,
    PriorityLevel.P2_ROUTINE: INSIDE_WASH,
}

LANGUAGE_NAME = {
    "hi": "Hindi",
    "mr": "Marathi",
    "ta": "Tamil",
    "te": "Telugu",
    "en": "English",
    "gu": "Gujarati",
    "bn": "Bengali",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
}


def language_name(code: str) -> str:
    return LANGUAGE_NAME.get(code, code.upper())


# IBM Plex: drawn for technical instrumentation, and its Devanagari, Tamil and
# Telugu siblings let patient-language previews speak in the same voice.
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+Condensed:wght@500;600&family=IBM+Plex+Sans:wght@400;450;500;600;700&family=IBM+Plex+Sans+Devanagari:wght@400;500&display=swap');

:root {{
  --ink: {INK};
  --graphite: {GRAPHITE};
  --slate: {SLATE};
  --muted: {MUTED};
  --line: {LINE};
  --hairline: {HAIRLINE};
  --paper: {PAPER};
  --surface: {SURFACE};
  --focus: {FOCUS};
  --below: {BELOW};
  --inside: {INSIDE};
  --above: {ABOVE};
  --quiet: {QUIET};
}}

html, body, .stApp, [class*="css"] {{
  font-family: 'IBM Plex Sans', 'IBM Plex Sans Devanagari', -apple-system, sans-serif;
  -webkit-font-smoothing: antialiased;
}}
.stApp {{ background: var(--paper); }}
#MainMenu, footer, header, [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stToolbar"], [data-testid="stDecoration"] {{ display: none !important; }}
.block-container {{ padding: 1.25rem 2rem 4rem; max-width: 1560px; }}

h1, h2, h3, h4 {{ color: var(--ink); font-weight: 600; letter-spacing: -0.015em; }}

/* ---------- instrument legends ---------- */
.gs-legend {{
  font-family: 'IBM Plex Sans Condensed', sans-serif;
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.1em; color: var(--muted);
}}
.gs-mono {{ font-family: 'IBM Plex Mono', monospace; font-variant-numeric: tabular-nums; }}

/* ---------- masthead ---------- */
.gs-masthead {{
  display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap;
  padding: 0 2px 14px; border-bottom: 1px solid var(--line); margin-bottom: 18px;
}}
.gs-mark {{
  font-size: 17px; font-weight: 700; color: var(--ink); letter-spacing: -0.02em;
  display: inline-flex; align-items: center; gap: 9px;
}}
.gs-mark::before {{
  content: ""; width: 3px; height: 17px; background: var(--ink); border-radius: 1px;
}}
.gs-masthead__clinic {{ font-size: 13px; color: var(--slate); }}
.gs-masthead__spacer {{ flex: 1 1 auto; }}
.gs-channel {{
  font-family: 'IBM Plex Mono', monospace; font-size: 11.5px; color: var(--slate);
  border: 1px solid var(--line); border-radius: 3px; padding: 3px 9px; background: var(--surface);
}}
.gs-channel b {{ color: var(--ink); font-weight: 500; }}

/* ---------- the round strip ---------- */
.gs-round {{
  display: flex; gap: 0; flex-wrap: wrap;
  background: var(--surface); border: 1px solid var(--line); border-radius: 6px;
  overflow: hidden; margin-bottom: 14px;
}}
.gs-round__cell {{
  flex: 1 1 150px; padding: 13px 18px; border-right: 1px solid var(--hairline);
}}
.gs-round__cell:last-child {{ border-right: none; }}
.gs-round__n {{
  font-family: 'IBM Plex Mono', monospace; font-size: 27px; font-weight: 500;
  line-height: 1.05; letter-spacing: -0.02em; font-variant-numeric: tabular-nums;
}}
.gs-round__label {{
  font-family: 'IBM Plex Sans Condensed', sans-serif; font-size: 11px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.1em; color: var(--ink); margin-top: 4px;
}}
.gs-round__note {{ font-size: 11.5px; color: var(--muted); margin-top: 1px; }}

/* ---------- critical bar ---------- */
.gs-critical {{
  display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
  background: {BELOW_WASH}; border: 1px solid #edcdc3; border-left: 3px solid var(--below);
  border-radius: 6px; padding: 12px 18px; margin-bottom: 14px;
}}
.gs-critical__tag {{
  font-family: 'IBM Plex Sans Condensed', sans-serif; font-size: 11px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.11em; color: var(--below);
}}
.gs-critical__body {{ font-size: 13.5px; color: #7d2c19; }}
a.gs-critical__who, a.gs-critical__who:visited {{
  font-weight: 600; color: #7d2c19 !important;
  text-decoration: underline !important; text-underline-offset: 2px;
}}
a.gs-critical__who:hover {{ color: var(--below) !important; }}

/* ---------- roster ---------- */
.gs-roster {{
  background: var(--surface); border: 1px solid var(--line); border-radius: 6px; overflow: hidden;
}}
.gs-roster__head, .gs-row {{
  display: grid; align-items: center;
  grid-template-columns: 3px minmax(200px, 1.5fr) 208px 116px 92px 104px 76px;
  gap: 18px; padding: 0 18px 0 0;
}}
.gs-roster__head {{
  padding-top: 9px; padding-bottom: 9px; border-bottom: 1px solid var(--line);
  background: #fbfcfd;
}}
.gs-roster__head span {{
  font-family: 'IBM Plex Sans Condensed', sans-serif; font-size: 10.5px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted);
}}
/* Headings sit over the edge their column is aligned to. */
.gs-roster__head span:nth-child(4), .gs-roster__head span:nth-child(5),
.gs-roster__head span:nth-child(6), .gs-roster__head span:nth-child(7) {{ text-align: right; }}
/* Streamlit styles every markdown link; the roster row is a surface, not a link. */
.gs-roster a.gs-row, .gs-roster a.gs-row:hover, .gs-roster a.gs-row:visited,
a.gs-back, a.gs-back:hover, a.gs-back:visited {{
  text-decoration: none !important; color: inherit !important;
}}
.gs-row {{
  border-bottom: 1px solid var(--hairline);
  transition: background 120ms ease;
}}
.gs-row:last-child {{ border-bottom: none; }}
.gs-row:hover {{ background: #fafbfc; }}
.gs-row:focus-visible {{ outline: 2px solid var(--focus); outline-offset: -2px; }}
.gs-row--on {{ background: #f4f6f8; }}
.gs-row__flag {{ height: 100%; min-height: 62px; }}
.gs-row__who {{ padding: 13px 0; min-width: 0; }}
.gs-row__name {{
  display: block; font-size: 15px; font-weight: 600; color: var(--ink);
  letter-spacing: -0.01em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.gs-row__meta {{
  display: block; font-size: 11.5px; color: var(--muted); margin-top: 2px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.gs-row__meta .gs-mono {{ color: var(--slate); }}
.gs-row__trace {{ display: block; line-height: 0; }}
.gs-row__value {{ text-align: right; }}
.gs-row__mg {{
  font-family: 'IBM Plex Mono', monospace; font-size: 21px; font-weight: 500;
  letter-spacing: -0.02em; font-variant-numeric: tabular-nums; display: block; line-height: 1.1;
}}
.gs-row__unit {{ display: block; font-size: 10.5px; color: var(--muted); margin-top: 2px; }}
.gs-row__when {{ font-size: 12.5px; color: var(--slate); text-align: right; }}
.gs-row__corridor {{ text-align: right; }}
.gs-row__pct {{
  font-family: 'IBM Plex Mono', monospace; font-size: 15px; font-weight: 500; color: var(--ink);
  font-variant-numeric: tabular-nums;
}}
.gs-row__pct i {{ font-style: normal; font-size: 11px; color: var(--muted); }}
.gs-row__bar {{
  display: block; height: 3px; background: var(--hairline); border-radius: 2px;
  margin-top: 5px; overflow: hidden;
}}
.gs-row__bar span {{ display: block; height: 100%; border-radius: 2px; }}
.gs-row__alerts {{ text-align: right; }}
.gs-pip {{
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 21px; height: 21px; padding: 0 6px; border-radius: 3px;
  font-family: 'IBM Plex Mono', monospace; font-size: 12px; font-weight: 600; color: #fff;
}}
.gs-pip--none {{ color: var(--muted); background: transparent; font-weight: 400; }}

/* ---------- record ---------- */
.gs-back {{
  display: inline-block; font-size: 12.5px; margin-bottom: 12px;
}}
.gs-back, .gs-back:visited {{ color: var(--slate) !important; }}
.gs-back:hover {{ color: var(--ink) !important; }}
.gs-record {{
  background: var(--surface); border: 1px solid var(--line); border-radius: 6px;
  padding: 20px 22px; margin-bottom: 14px;
}}
.gs-record__top {{ display: flex; justify-content: space-between; gap: 24px; flex-wrap: wrap; }}
.gs-record__name {{
  font-size: 25px; font-weight: 600; color: var(--ink); letter-spacing: -0.025em; line-height: 1.15;
}}
.gs-record__meta {{ font-size: 13px; color: var(--slate); margin-top: 5px; }}
.gs-record__ids {{
  font-family: 'IBM Plex Mono', monospace; font-size: 11.5px; color: var(--muted); margin-top: 3px;
}}
.gs-corridor {{ text-align: right; }}
.gs-corridor__v {{
  font-family: 'IBM Plex Mono', monospace; font-size: 17px; font-weight: 500; color: var(--ink);
  letter-spacing: -0.01em; margin-top: 3px;
}}
.gs-rx {{
  margin-top: 15px; padding-top: 13px; border-top: 1px solid var(--hairline);
  font-size: 13.5px; color: var(--graphite);
}}
.gs-note {{ font-size: 12.5px; color: var(--muted); margin-top: 7px; font-style: italic; }}

.gs-vitals {{ display: flex; gap: 0; flex-wrap: wrap; margin-bottom: 14px;
  background: var(--surface); border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }}
.gs-vitals__cell {{ flex: 1 1 130px; padding: 13px 18px; border-right: 1px solid var(--hairline); }}
.gs-vitals__cell:last-child {{ border-right: none; }}
.gs-vitals__v {{
  font-family: 'IBM Plex Mono', monospace; font-size: 24px; font-weight: 500;
  letter-spacing: -0.02em; line-height: 1.1; font-variant-numeric: tabular-nums; margin-top: 5px;
}}
.gs-vitals__n {{ font-size: 11.5px; color: var(--muted); margin-top: 2px; }}

/* ---------- alerts ---------- */
/* The header card and the expander beneath it are one alert; square the seam
   between them and let the border-left run through both. */
.gs-alert {{
  border: 1px solid var(--line); border-left: 3px solid var(--slate);
  border-radius: 6px 6px 0 0; border-bottom: none;
  padding: 14px 18px; background: var(--surface);
}}
[data-testid="stElementContainer"]:has(.gs-alert)
  + [data-testid="stLayoutWrapper"] [data-testid="stExpander"] {{
  border-radius: 0 0 6px 6px; border-top: none; margin-bottom: 14px;
}}
.gs-alert__top {{ display: flex; justify-content: space-between; gap: 18px; flex-wrap: wrap; }}
.gs-alert__tag {{
  font-family: 'IBM Plex Sans Condensed', sans-serif; font-size: 10.5px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.11em;
}}
.gs-alert__name {{ font-size: 16px; font-weight: 600; color: var(--ink); margin-top: 5px; }}
.gs-alert__meta {{ font-size: 11.5px; color: var(--muted); margin-top: 2px; }}
.gs-alert__read {{
  font-family: 'IBM Plex Mono', monospace; font-size: 27px; font-weight: 500;
  letter-spacing: -0.025em; text-align: right; line-height: 1;
}}
.gs-alert__unit {{ font-size: 10.5px; color: var(--muted); text-align: right; margin-top: 4px; }}

.gs-said {{
  border-left: 2px solid var(--line); padding: 3px 0 3px 13px;
  font-size: 14px; color: var(--ink); line-height: 1.55;
}}
.gs-said--translated {{ font-size: 12.5px; color: var(--muted); margin-top: 5px; }}
.gs-out {{
  background: {INSIDE_WASH}; border: 1px solid #d8e7df; border-radius: 5px;
  padding: 10px 13px; font-size: 13px; color: #1f3d2f; line-height: 1.55;
}}
.gs-in {{
  background: var(--paper); border: 1px solid var(--line); border-radius: 5px;
  padding: 10px 13px; font-size: 13px; color: var(--ink); line-height: 1.55;
}}
.gs-stamp {{
  font-family: 'IBM Plex Mono', monospace; font-size: 10.5px; color: var(--muted);
  margin: 9px 0 3px;
}}
.gs-facts {{ font-size: 13.5px; color: var(--graphite); line-height: 1.75; }}
.gs-facts b {{ font-family: 'IBM Plex Mono', monospace; font-weight: 600; color: var(--ink); }}

.gs-empty {{
  border: 1px dashed var(--line); border-radius: 6px; padding: 30px 20px;
  text-align: center; color: var(--slate); font-size: 13.5px; background: var(--surface);
}}
.gs-empty b {{ display: block; color: var(--ink); font-size: 15px; font-weight: 600; margin-bottom: 4px; }}

/* ---------- section nav, built from a radio ---------- */
[data-testid="stRadio"] > label {{ display: none; }}
[data-testid="stRadio"] [role="radiogroup"] {{
  gap: 0; border-bottom: 1px solid var(--line); margin-bottom: 16px;
}}
[data-testid="stRadio"] [role="radiogroup"] > label {{
  margin: 0; padding: 9px 18px 10px; cursor: pointer;
  border-bottom: 2px solid transparent; transition: color 120ms ease, border-color 120ms ease;
}}
[data-testid="stRadio"] [role="radiogroup"] > label:hover {{ border-bottom-color: var(--line); }}
[data-testid="stRadio"] [role="radiogroup"] > label > span:first-child,
[data-testid="stRadio"] [role="radiogroup"] > label > div:first-child {{ display: none !important; }}
[data-testid="stRadio"] [role="radiogroup"] > label p {{
  font-family: 'IBM Plex Sans Condensed', sans-serif; font-size: 12.5px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.09em; color: var(--muted); margin: 0;
}}
[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) {{
  border-bottom-color: var(--ink);
}}
[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) p {{ color: var(--ink); }}
[data-testid="stRadio"] [role="radiogroup"] > label:focus-within {{
  outline: 2px solid var(--focus); outline-offset: -2px; border-radius: 3px;
}}

/* ---------- streamlit controls ---------- */
.stButton button, .stLinkButton a, .stFormSubmitButton button {{
  border-radius: 4px; font-family: 'IBM Plex Sans', sans-serif; font-size: 13px;
  font-weight: 500; letter-spacing: 0; border: 1px solid var(--line);
  transition: background 120ms ease, border-color 120ms ease;
}}
/* Buttons and link buttons share these testids, so both weights stay legible. */
[data-testid$="Button-secondary"] {{ color: var(--ink); }}
[data-testid$="Button-primary"] {{
  background: var(--ink) !important; border-color: var(--ink) !important; color: #fff !important;
}}
[data-testid$="Button-primary"]:hover {{
  background: #232c3c !important; border-color: #232c3c !important;
}}
.stButton button:focus-visible, .stLinkButton a:focus-visible {{
  outline: 2px solid var(--focus); outline-offset: 1px;
}}
.stTextInput input, .stTextArea textarea, .stNumberInput input {{
  border-radius: 4px; font-size: 13.5px; border-color: var(--line);
}}
.stTextArea textarea {{ font-family: 'IBM Plex Sans', 'IBM Plex Sans Devanagari', sans-serif; }}
div[data-baseweb="select"] > div {{ border-radius: 4px; border-color: var(--line); font-size: 13.5px; }}
button[role="tab"] {{ font-size: 13.5px; font-weight: 500; color: var(--slate); }}
button[role="tab"][aria-selected="true"] {{ color: var(--ink); font-weight: 600; }}
[data-baseweb="tab-highlight"] {{ background: var(--ink) !important; }}
[data-baseweb="tab-border"] {{ background: var(--line) !important; }}
[data-testid="stExpander"] {{ border-color: var(--line); border-radius: 6px; background: var(--surface); }}
[data-testid="stExpander"] summary {{ font-size: 13px; color: var(--slate); }}
hr {{ border-color: var(--line); margin: 1.1rem 0; }}
[data-testid="stCaptionContainer"] p {{ font-size: 12px; color: var(--muted); }}

@media (max-width: 1180px) {{
  .gs-roster__head, .gs-row {{ grid-template-columns: 3px minmax(160px, 1.4fr) 116px 92px 76px; }}
  .gs-roster__head span:nth-child(3), .gs-row__trace,
  .gs-roster__head span:nth-child(6), .gs-row__corridor {{ display: none; }}
}}
@media (max-width: 760px) {{
  .block-container {{ padding: 1rem 1rem 3rem; }}
  .gs-roster__head, .gs-row {{ grid-template-columns: 3px 1fr 96px; }}
  .gs-roster__head span:nth-child(5), .gs-row__when,
  .gs-roster__head span:nth-child(7), .gs-row__alerts {{ display: none; }}
}}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ transition: none !important; animation: none !important; }}
}}
</style>
"""
