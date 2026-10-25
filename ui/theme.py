# ui/theme.py
"""
Design system for the Streamlit UI: palette, CSS and small HTML components.

Every dynamic value goes through esc() before it is placed in HTML, so stop names, tool results
or any other text can never inject markup. LLM text is NOT rendered through this module - it is
shown with st.markdown() (no unsafe HTML).
"""
from __future__ import annotations

import html

NAVY = "#0F2747"
BLUE = "#2563EB"
INK = "#0F172A"
MUTED = "#64748B"
LINE = "#E2E8F0"

MODE_COLORS = {"Car": "#F97316", "Bus": "#2563EB", "Metro": "#16A34A"}
MODE_ICONS = {"Car": "🚗", "Bus": "🚌", "Metro": "🚇"}


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def compact(markup: str) -> str:
    """Streamlit's markdown turns indented / blank-line-separated HTML into code blocks, so flatten it."""
    return "".join(line.strip() for line in markup.splitlines())


CSS = """
<style>
.block-container { padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1180px; }
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }

/* ---------- sidebar ---------- */
@media (min-width: 900px) {
  section[data-testid="stSidebar"][aria-expanded="true"] { min-width: 340px; max-width: 340px; }
}
[data-testid="stSidebar"] { border-right: 1px solid rgba(255,255,255,.08); }
[data-testid="stSidebar"] .block-container, [data-testid="stSidebarUserContent"] { padding-top: 1.2rem; }
.umo-brand { display:flex; align-items:center; gap:12px; margin: 4px 0 4px; }
.umo-logo { width:42px; height:42px; border-radius:12px; background:linear-gradient(135deg,#3B82F6,#06B6D4);
  display:flex; align-items:center; justify-content:center; font-size:22px; box-shadow:0 4px 12px rgba(0,0,0,.25); }
.umo-brand-title { color:#fff; font-weight:700; font-size:1.08rem; line-height:1.2; }
.umo-brand-sub { color:#9FB4D3; font-size:.8rem; }
.umo-side-label { color:#9FB4D3; font-size:.72rem; letter-spacing:.08em; text-transform:uppercase;
  font-weight:700; margin: 18px 0 2px; }
.umo-side-note { color:#9FB4D3; font-size:.78rem; line-height:1.4; margin-bottom:6px; }
[data-testid="stSidebar"] label p, [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { color:#DCE6F5 !important; font-weight:600; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.12); }
[data-testid="stSidebar"] .stButton button { border-radius: 10px; font-weight: 600; }
[data-testid="stSidebar"] [data-testid="stExpander"] { border:1px solid rgba(255,255,255,.14); border-radius:10px; background: rgba(255,255,255,.04); }

/* ---------- banner ---------- */
.umo-banner { background: linear-gradient(120deg,#0F2747 0%,#1D4ED8 100%); color:#fff; border-radius:16px;
  padding:22px 28px; box-shadow:0 8px 22px rgba(15,39,71,.20); }
.umo-title { font-size:1.7rem; font-weight:800; letter-spacing:-.01em; margin:0; }
.umo-subtitle { margin:.3rem 0 0; color:#CFE0FF; font-size:.97rem; }
.umo-pills { margin-top:14px; display:flex; flex-wrap:wrap; gap:8px; }
.umo-pill { background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.22); color:#fff;
  padding:4px 12px; border-radius:999px; font-size:.78rem; font-weight:600; }

/* ---------- route header ---------- */
.umo-route { display:flex; align-items:center; gap:14px; flex-wrap:wrap; background:#fff; border:1px solid #E2E8F0;
  border-radius:14px; padding:14px 18px; margin-top:16px; box-shadow:0 1px 2px rgba(15,23,42,.04); }
.umo-stop { font-weight:700; color:#0F172A; font-size:1.02rem; }
.umo-dot { display:inline-block; width:11px; height:11px; border-radius:50%; margin-right:8px; vertical-align:middle; }
.umo-arrow { color:#94A3B8; font-size:1.2rem; }
.umo-route-tag { margin-left:auto; }

/* ---------- KPI cards ---------- */
.umo-kpis { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin-top:14px; }
.umo-kpi { background:#fff; border:1px solid #E2E8F0; border-radius:14px; padding:14px 16px 12px;
  box-shadow:0 1px 2px rgba(15,23,42,.04); }
.umo-kpi-label { color:#64748B; font-size:.72rem; font-weight:700; letter-spacing:.07em; text-transform:uppercase; }
.umo-kpi-value { color:#0F172A; font-size:1.75rem; font-weight:800; line-height:1.25; margin-top:2px; }
.umo-kpi-unit { color:#64748B; font-size:.95rem; font-weight:600; margin-left:4px; }
.umo-kpi-sub { color:#64748B; font-size:.8rem; margin-top:2px; }

/* ---------- recommendation strip ---------- */
.umo-reco { display:flex; align-items:center; gap:14px; flex-wrap:wrap; margin-top:16px; border-radius:14px;
  padding:14px 20px; background:linear-gradient(90deg,#ECFDF5,#F0F9FF); border:1px solid #BBF7D0; }
.umo-reco-label { color:#166534; font-size:.72rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }
.umo-reco-main { font-size:1.25rem; font-weight:800; color:#0F172A; }
.umo-reco-why { color:#334155; font-size:.92rem; }

.umo-note { margin-top:12px; background:#FFFBEB; border:1px solid #FDE68A; color:#92400E; border-radius:12px;
  padding:10px 16px; font-size:.88rem; line-height:1.45; }

/* ---------- section titles ---------- */
.umo-section { display:flex; align-items:center; gap:10px; font-size:1.08rem; font-weight:800; color:#0F172A; margin:26px 0 10px; }
.umo-section:before { content:""; width:5px; height:20px; border-radius:3px; background:#2563EB; }

/* ---------- mode cards ---------- */
.umo-modes { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }
.umo-mode { position:relative; background:#fff; border:1px solid #E2E8F0; border-top:4px solid var(--c); border-radius:14px;
  padding:16px 18px; box-shadow:0 1px 2px rgba(15,23,42,.04); }
.umo-mode.best { box-shadow:0 0 0 2px #2563EB, 0 10px 24px rgba(37,99,235,.14); }
.umo-mode.off { opacity:.72; background:#F8FAFC; border-top-color:#CBD5E1; }
.umo-ribbon { position:absolute; top:-12px; right:14px; background:#2563EB; color:#fff; font-size:.68rem; font-weight:800;
  letter-spacing:.08em; padding:3px 10px; border-radius:999px; }
.umo-mode-head { display:flex; align-items:center; gap:10px; font-weight:800; font-size:1.05rem; color:#0F172A; }
.umo-mode-icon { font-size:1.5rem; }
.umo-mode-cost { font-size:1.9rem; font-weight:800; color:#0F172A; margin-top:10px; line-height:1.1; }
.umo-mode-time { color:#334155; font-size:1rem; font-weight:600; margin-top:2px; }
.umo-mode-meta { margin-top:10px; display:flex; flex-wrap:wrap; gap:6px; }
.umo-mode-why { color:#64748B; font-size:.83rem; margin-top:10px; line-height:1.4; }

/* ---------- badges ---------- */
.umo-badge { display:inline-block; padding:2px 10px; border-radius:999px; font-size:.72rem; font-weight:700; }
.b-green { background:#DCFCE7; color:#166534; } .b-blue { background:#DBEAFE; color:#1E40AF; }
.b-grey { background:#E2E8F0; color:#475569; }  .b-amber { background:#FEF3C7; color:#92400E; }
.b-red { background:#FEE2E2; color:#991B1B; }   .b-navy { background:#0F2747; color:#fff; }

/* ---------- cards built from st.container(key=...) ---------- */
[class*="st-key-card_"] { background:#fff; border:1px solid #E2E8F0; border-radius:14px; padding:18px 20px;
  box-shadow:0 1px 2px rgba(15,23,42,.04); }
[class*="st-key-card_"] p { line-height:1.55; }
.umo-card-title { display:flex; align-items:center; justify-content:space-between; gap:10px; font-weight:800;
  font-size:1.02rem; color:#0F172A; margin-bottom:8px; }
[data-testid="stDeckGlJsonChart"] { border-radius:12px; overflow:hidden; border:1px solid #E2E8F0; }

/* ---------- legend ---------- */
.umo-legend { display:flex; flex-wrap:wrap; gap:18px; margin-top:10px; color:#334155; font-size:.86rem; }
.umo-legend span { display:inline-flex; align-items:center; gap:7px; }
.umo-swatch { width:12px; height:12px; border-radius:50%; display:inline-block; }
.umo-line { width:22px; height:5px; border-radius:3px; background:#2563EB; display:inline-block; }

/* ---------- trace timeline ---------- */
.umo-trace { width:100%; border-collapse:collapse; font-size:.86rem; }
.umo-trace th { text-align:left; color:#64748B; font-size:.7rem; letter-spacing:.07em; text-transform:uppercase;
  padding:8px 10px; border-bottom:2px solid #E2E8F0; }
.umo-trace td { padding:9px 10px; border-bottom:1px solid #EEF2F7; vertical-align:top; color:#0F172A; }
.umo-trace tr:hover td { background:#F8FAFC; }
.umo-code { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:.82rem; color:#1E293B; }
.umo-muted { color:#64748B; }

/* ---------- empty state ---------- */
.umo-steps { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin-top:6px; }
.umo-step { background:#fff; border:1px solid #E2E8F0; border-radius:14px; padding:16px; }
.umo-step-n { width:28px; height:28px; border-radius:50%; background:#DBEAFE; color:#1E40AF; font-weight:800;
  display:flex; align-items:center; justify-content:center; margin-bottom:8px; }
.umo-step b { color:#0F172A; } .umo-step p { margin:.3rem 0 0; color:#64748B; font-size:.85rem; line-height:1.45; }

.umo-footer { text-align:center; color:#94A3B8; font-size:.78rem; line-height:1.6; margin-top:34px; padding-top:16px;
  border-top:1px solid #E2E8F0; }
.umo-footer a { color:#64748B; }

@media (max-width: 900px) {
  .umo-kpis { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .umo-modes, .umo-steps { grid-template-columns:1fr; }
}
@media print {
  [data-testid="stSidebar"], header[data-testid="stHeader"] { display:none !important; }
  .block-container { max-width:100% !important; }
}
</style>
"""


# --------------------------------------------------------------------------- components
def badge(text: str, kind: str = "grey") -> str:
    return f'<span class="umo-badge b-{kind}">{esc(text)}</span>'


def brand() -> str:
    return compact(f"""
    <div class="umo-brand"><div class="umo-logo">🚦</div>
    <div><div class="umo-brand-title">Urban Mobility AI</div>
    <div class="umo-brand-sub">Hyderabad Smart Travel</div></div></div>""")


def banner(title: str, subtitle: str, pills: list[str]) -> str:
    chips = "".join(f'<span class="umo-pill">{esc(p)}</span>' for p in pills)
    return compact(f"""
    <div class="umo-banner"><div class="umo-title">{esc(title)}</div>
    <div class="umo-subtitle">{esc(subtitle)}</div><div class="umo-pills">{chips}</div></div>""")


def route_header(source: str, destination: str, tag: str) -> str:
    return compact(f"""
    <div class="umo-route">
    <span class="umo-stop"><span class="umo-dot" style="background:#16A34A"></span>{esc(source)}</span>
    <span class="umo-arrow">→</span>
    <span class="umo-stop"><span class="umo-dot" style="background:#DC2626"></span>{esc(destination)}</span>
    <span class="umo-route-tag">{tag}</span></div>""")


def kpi(label: str, value, unit: str = "", sub: str = "") -> str:
    unit_html = f'<span class="umo-kpi-unit">{esc(unit)}</span>' if unit else ""
    sub_html = f'<div class="umo-kpi-sub">{esc(sub)}</div>' if sub else '<div class="umo-kpi-sub">&nbsp;</div>'
    return compact(f"""
    <div class="umo-kpi"><div class="umo-kpi-label">{esc(label)}</div>
    <div class="umo-kpi-value">{esc(value)}{unit_html}</div>{sub_html}</div>""")


def kpi_row(cards: list[str]) -> str:
    return f'<div class="umo-kpis">{"".join(cards)}</div>'


def recommendation(mode: str, cost: float, minutes: float, reason: str) -> str:
    return compact(f"""
    <div class="umo-reco"><div><div class="umo-reco-label">Recommended</div>
    <div class="umo-reco-main">{MODE_ICONS.get(mode, '')} {esc(mode)} &nbsp;·&nbsp; ₹{cost:,.2f} &nbsp;·&nbsp; {minutes:.0f} min</div></div>
    <div class="umo-reco-why">{esc(reason)}</div></div>""")


def note(text: str) -> str:
    return f'<div class="umo-note">ℹ️ {esc(text)}</div>'


def recommendation_walk(minutes: int, km: float) -> str:
    why = (f"Only {km:.2f} km. The options below leave out waiting for, and walking to, a stop, "
           "so for trips this short compare them with walking.")
    return compact(f"""
    <div class="umo-reco"><div><div class="umo-reco-label">Short trip</div>
    <div class="umo-reco-main">🚶 Walk &nbsp;·&nbsp; about {minutes} min</div></div>
    <div class="umo-reco-why">{esc(why)}</div></div>""")


def section(title: str) -> str:
    return f'<div class="umo-section">{esc(title)}</div>'


def mode_card(name: str, option: dict | None, status: str, best: bool, cheapest: bool,
              fastest: bool, why_not: str = "") -> str:
    color = MODE_COLORS.get(name, "#64748B")
    icon = MODE_ICONS.get(name, "")
    classes = "umo-mode" + (" best" if best else "") + (" off" if option is None else "")
    ribbon = '<div class="umo-ribbon">RECOMMENDED</div>' if best else ""
    if option is None:
        body = (f'<div class="umo-mode-cost">—</div>'
                f'<div class="umo-mode-meta">{badge("Not available for this trip", "grey")}</div>'
                f'<div class="umo-mode-why">{esc(why_not)}</div>')
    else:
        tags = ""
        if cheapest:
            tags += badge("Cheapest", "green") + " "
        if fastest:
            tags += badge("Fastest", "blue") + " "
        if status == "Not checked":
            tags += badge("Availability not checked", "amber")
        body = (f'<div class="umo-mode-cost">₹{option["cost"]:,.2f}</div>'
                f'<div class="umo-mode-time">{option["time"]:.0f} min</div>'
                f'<div class="umo-mode-meta">{tags}</div>')
    return compact(f'<div class="{classes}" style="--c:{color}">{ribbon}'
                   f'<div class="umo-mode-head"><span class="umo-mode-icon">{icon}</span>{esc(name)}</div>') + body + "</div>"


def mode_row(cards: list[str]) -> str:
    return f'<div class="umo-modes">{"".join(cards)}</div>'


def card_title(title: str, right_html: str = "") -> str:
    return f'<div class="umo-card-title"><span>{esc(title)}</span><span>{right_html}</span></div>'


def legend(source: str, destination: str, km: float) -> str:
    return compact(f"""
    <div class="umo-legend">
    <span><i class="umo-swatch" style="background:#16A34A"></i>Start · {esc(source)}</span>
    <span><i class="umo-swatch" style="background:#DC2626"></i>Destination · {esc(destination)}</span>
    <span><i class="umo-line"></i>Shortest drivable route · {km:.2f} km</span></div>""")


_STATUS_KIND = {"ok": "green", "fallback": "amber", "error": "red", "skipped": "grey"}


def trace_table(trace: list[dict]) -> str:
    rows = []
    for t in trace:
        actor = badge("LLM agent", "blue") if t["actor"] == "agent" else badge("Fixed code", "grey")
        args = f'<span class="umo-code">{esc(_fmt_args(t["args"]))}</span>' if t["args"] else '<span class="umo-muted">—</span>'
        rows.append(
            f'<tr><td>{esc(t["step"])}</td><td>{actor}</td><td><span class="umo-code">{esc(t["tool"])}</span></td>'
            f'<td>{args}</td><td>{badge(t["status"], _STATUS_KIND.get(t["status"], "grey"))}</td>'
            f'<td class="umo-muted">{esc(t["ms"])} ms</td><td>{esc(t["summary"])}</td></tr>')
    head = ("<tr><th>#</th><th>Decided by</th><th>Tool</th><th>Arguments</th><th>Status</th>"
            "<th>Time</th><th>Result</th></tr>")
    return compact(f'<table class="umo-trace"><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table>')


def _fmt_args(args: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in args.items())


def empty_state_steps() -> str:
    steps = [
        ("Route", "Shortest drivable path (Dijkstra) over 137k road points of Hyderabad."),
        ("Context", "Nearest bus stops and metro stations from the Neo4j city graph, plus live weather."),
        ("Compare", "Cost and time estimates for car, bus and metro, with unavailable modes explained."),
        ("Explain", "An LLM turns the computed facts into a short, grounded recommendation."),
    ]
    cards = "".join(f'<div class="umo-step"><div class="umo-step-n">{i}</div><b>{esc(t)}</b><p>{esc(d)}</p></div>'
                    for i, (t, d) in enumerate(steps, 1))
    return f'<div class="umo-steps">{cards}</div>'


def footer(assumptions: str, model: str) -> str:
    return ('<div class="umo-footer">Estimates: ' + esc(assumptions) + '<br>'
            'Map data © OpenStreetMap contributors &nbsp;·&nbsp; Basemap © CARTO &nbsp;·&nbsp; '
            'Weather data by Open-Meteo.com (CC BY 4.0) &nbsp;·&nbsp; '
            'Explanations by ' + esc(model) + ' on Groq</div>')
