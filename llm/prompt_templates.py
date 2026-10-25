# llm/prompt_templates.py
"""
Builds the facts the LLM is allowed to talk about, and the prompt around them.

Everything numeric (cheapest / fastest / balanced mode, availability) is computed here in
plain Python so the LLM only has to explain it, not calculate it. The old prompt asked the
model to discuss "historical movement patterns", which do not exist in the data and invited
invented content; this one forbids inventing anything.
"""
from agents.cost_agent import CostAgent

MODES = [("Car", "car"), ("Bus", "bus"), ("Metro", "metro")]


def _pick_balanced(options: dict) -> str | None:
    """Lowest combined (cost / max cost) + (time / max time) across the available modes."""
    if not options:
        return None
    max_cost = max(o["cost"] for o in options.values()) or 1
    max_time = max(o["time"] for o in options.values()) or 1
    return min(options, key=lambda m: options[m]["cost"] / max_cost + options[m]["time"] / max_time)


def build_trip_facts(distance_km, cost, weather=None, transport=None, graph_context=None,
                     straight_line_km=None, source_label=None, destination_label=None, walk_min=None) -> dict:
    transport_checked = transport is not None
    options = {}
    status = {}
    for name, key in MODES:
        c, t = cost.get(f"{key}_cost_rs"), cost.get(f"{key}_time_min")
        if c is None or t is None:
            status[name] = "not available (no stop within range at both ends)"
            continue
        options[name] = {"cost": c, "time": t}
        if name == "Car" or transport_checked:
            status[name] = "available"
        else:
            status[name] = "availability not checked"

    return {
        "source": source_label,
        "destination": destination_label,
        "distance_km": distance_km,
        "straight_line_km": straight_line_km,
        "options": options,
        "status": status,
        "cheapest": min(options, key=lambda m: options[m]["cost"]) if options else None,
        "fastest": min(options, key=lambda m: options[m]["time"]) if options else None,
        "balanced": _pick_balanced(options),
        "weather": weather if weather and weather.get("avg_temperature") is not None else None,
        "walk_min": walk_min,
        "weather_checked": weather is not None,
        "transport_checked": transport_checked,
        "graph_summary": (graph_context or {}).get("summary") if graph_context else None,
        "assumptions": CostAgent.ASSUMPTIONS,
    }


def format_facts(f: dict) -> str:
    lines = []
    if f.get("source") and f.get("destination"):
        lines.append(f"Trip: {f['source']} -> {f['destination']} (Hyderabad)")
    lines.append(f"Road distance (shortest drivable route): {f['distance_km']} km")
    if f.get("straight_line_km") is not None:
        lines.append(f"Straight-line distance: {f['straight_line_km']} km")

    if f.get("walk_min") is not None:
        lines.append(f"Walking: about {f['walk_min']} min on foot at 5 km/h. This is a very short trip, and the "
                     "motorised estimates below leave out waiting for, and walking to, a stop.")
    lines.append("Options:")
    for name, _ in MODES:
        opt = f["options"].get(name)
        if opt:
            lines.append(f"- {name}: Rs {opt['cost']:.2f}, {opt['time']:.1f} min [{f['status'][name]}]")
        else:
            lines.append(f"- {name}: {f['status'].get(name, 'not available')}")

    if f.get("walk_min") is not None:
        lines.append(f"Cheapest: {f['cheapest']}; Fastest: {f['fastest']}")
    else:
        lines.append(f"Cheapest: {f['cheapest']}; Fastest: {f['fastest']}; "
                     f"Most balanced (lowest combined normalised cost + time): {f['balanced']}")

    if f["weather"]:
        lines.append(f"Live weather at route midpoint: {f['weather']['avg_temperature']} C, "
                     f"wind {f['weather']['avg_windspeed']} km/h")
    elif f["weather_checked"]:
        lines.append("Live weather: lookup failed or returned nothing")
    else:
        lines.append("Live weather: not checked")

    lines.append("City graph facts: " + (f["graph_summary"] or "not retrieved"))
    lines.append("Estimate assumptions: " + f["assumptions"])
    return "\n".join(lines)


SYSTEM_PROMPT = (
    "You are a careful urban mobility analyst. You explain trip options using ONLY the facts "
    "you are given. Never invent numbers, places, traffic conditions or history. If a fact is "
    "marked 'not checked' or 'not retrieved', say it was not checked instead of guessing."
)


def walk_recommendation(f: dict) -> str:
    """Deterministic first line for very short trips (written by the app, never by the LLM)."""
    return (f"**Recommendation:** This is a very short trip - walking takes about {f['walk_min']} min. "
            "Compare that with the options below, which leave out waiting and walking to a stop.")


def explanation_prompt(facts: dict) -> str:
    if facts.get("walk_min") is not None:
        return f"""{format_facts(facts)}

This is a very short trip. The app already shows the recommendation (walking), so do NOT write a recommendation line.
Write at most 70 words of Markdown using exactly this structure:
- **If you ride:** the cheapest listed mode with its fare, and the fastest listed mode with its time. For any mode marked "availability not checked", say that its availability was not checked.
- **Conditions:** one sentence on weather and nearby stops. Leave this bullet out completely when no weather or stop facts were provided.

Rules: do not show calculations; do not recommend a motorised mode; do not ask questions. Finish with one short italic line saying the figures are estimates."""
    return f"""{format_facts(facts)}

Write a concise explanation (at most 130 words) in Markdown using exactly this structure:

**Recommendation:** one sentence naming the best mode and the main reason.
- **Cost:** which mode is cheapest and its fare.
- **Time:** which mode is fastest and its travel time.
- **Balance:** one sentence on the most balanced option.
- **Conditions:** one sentence on weather and nearby stops. Leave this bullet out completely when no weather or stop facts were provided.

Rules: if a Walking fact is present, mention walking in the Recommendation sentence; do not show calculations, formulas or unit arithmetic; do not repeat the assumptions list; do not ask questions. Finish with one short italic line saying the figures are estimates."""


def recommendation_reason(f: dict) -> str:
    """One deterministic sentence explaining why the balanced mode was recommended."""
    best = f.get("balanced")
    if not best:
        return ""
    caveat = "" if (f.get("transport_checked") or best == "Car") else " Bus and metro availability was not checked."
    if len(f["options"]) == 1:
        return f"{best} is the only available option for this trip." + caveat
    if best == f["cheapest"] == f["fastest"]:
        return f"{best} is both the cheapest and the fastest option." + caveat
    if best == f["cheapest"]:
        return f"{best} has the lowest cost and the best overall balance of cost and time." + caveat
    if best == f["fastest"]:
        return f"{best} is the fastest and the best overall balance of cost and time." + caveat
    return f"{best} gives the best balance of cost and time." + caveat


def template_explanation(f: dict) -> str:
    """Deterministic fallback used when the LLM is unavailable. Never contains invented content."""
    lines = []
    if f["options"]:
        best = f["balanced"]
        cheapest, fastest = f["options"][f["cheapest"]], f["options"][f["fastest"]]
        if f.get("walk_min") is not None:
            lines.append(walk_recommendation(f))
            ride = (f"- **If you ride:** {f['cheapest']} is cheapest at Rs {cheapest['cost']:.2f} and "
                    f"{f['fastest']} is fastest at {fastest['time']:.1f} min.")
            if not f.get("transport_checked") and (f["cheapest"] != "Car" or f["fastest"] != "Car"):
                ride += " Bus and metro availability was not checked."
            lines.append(ride)
        else:
            lines.append(f"**Recommendation:** {recommendation_reason(f)}")
            lines.append(f"- **Cost:** {f['cheapest']} is cheapest at Rs {cheapest['cost']:.2f}.")
            lines.append(f"- **Time:** {f['fastest']} is fastest at {fastest['time']:.1f} min.")
            lines.append(f"- **Balance:** {best} is the most balanced option.")
    else:
        lines.append(f"**Trip summary:** road distance {f['distance_km']} km.")
    unavailable = [n for n, s in f["status"].items() if s.startswith("not available")]
    if unavailable:
        lines.append("- **Not available:** " + ", ".join(unavailable) + ".")
    conditions = []
    if f["weather"]:
        conditions.append(f"{f['weather']['avg_temperature']} C with wind {f['weather']['avg_windspeed']} km/h at the route midpoint")
    if f["graph_summary"]:
        conditions.append(f["graph_summary"])
    if conditions:
        lines.append("- **Conditions:** " + ". ".join(conditions))
    lines.append("*Figures are estimates: " + f["assumptions"] + "*")
    return "\n".join(lines)
