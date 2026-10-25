# agents/tools.py
"""
Tool definitions for the LLM tool-calling agent.

The model never sees or passes raw coordinates: tools read the trip from a shared TripState,
so the model's job is to decide WHICH tools to call, in WHAT order, with what options, and
when to stop - not to copy numbers around (small LLMs are bad at that).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Callable

from routing.road_graph import DEFAULT_MAX_SNAP_M


@dataclass
class TripState:
    source: tuple
    destination: tuple
    source_label: str | None = None
    destination_label: str | None = None
    route: dict | None = None
    weather: dict | None = None
    transport: dict | None = None
    graph_context: dict | None = None

    @property
    def midpoint(self):
        return ((self.source[0] + self.destination[0]) / 2,
                (self.source[1] + self.destination[1]) / 2)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    fn: Callable[[TripState, dict], dict] = field(repr=False)

    def spec(self) -> dict:
        return {"type": "function",
                "function": {"name": self.name, "description": self.description,
                             "parameters": self.parameters}}


def _no_params():
    return {"type": "object", "properties": {}, "additionalProperties": False}


class ToolKit:
    """Wraps the existing agents as callable tools. The agent classes themselves are unchanged in role."""

    def __init__(self, route_agent, weather_agent, transport_agent, graph_rag_agent):
        self.route_agent = route_agent
        self.weather_agent = weather_agent
        self.transport_agent = transport_agent
        self.graph_rag_agent = graph_rag_agent
        self.tools = [
            Tool(
                "find_route",
                "Find the shortest drivable route between the start and destination and return its "
                "road distance. Call this FIRST. If it fails because a point is too far from a road, "
                "the error includes a hint; you may retry once with a larger max_snap_m.",
                {"type": "object",
                 "properties": {"max_snap_m": {
                     "type": "number",
                     "description": "How far (metres) a point may be from the nearest road. Default 1000."}},
                 "additionalProperties": False},
                self.find_route),
            Tool(
                "get_weather",
                "Get current temperature and wind speed from the live weather API.",
                {"type": "object",
                 "properties": {"location": {
                     "type": "string", "enum": ["midpoint", "source", "destination"],
                     "description": "Where to measure. Default midpoint."}},
                 "additionalProperties": False},
                self.get_weather),
            Tool(
                "check_transport",
                "Check whether a bus stop and a metro station are close to BOTH the start and the "
                "destination, using the city graph.",
                _no_params(), self.check_transport),
            Tool(
                "get_graph_context",
                "Retrieve facts about the area from the Neo4j city graph (nearest stops, stored "
                "weather) for the final explanation. Best called after check_transport.",
                _no_params(), self.get_graph_context),
        ]
        self.by_name = {t.name: t for t in self.tools}

    def specs(self) -> list[dict]:
        return [t.spec() for t in self.tools]

    # ----------------------------------------------------------------- tools
    def find_route(self, state: TripState, args: dict) -> dict:
        max_snap = args.get("max_snap_m", DEFAULT_MAX_SNAP_M)
        try:
            max_snap = min(max(float(max_snap), 100.0), 5000.0)
        except (TypeError, ValueError):
            max_snap = DEFAULT_MAX_SNAP_M

        route = self.route_agent.find_route(*state.source, *state.destination, max_snap_m=max_snap)
        if route is None:
            return {"ok": False, "error": self.route_agent.last_error or "No route found",
                    "hint": self.route_agent.last_hint}

        state.route = route
        km = round(route["distance_m"] / 1000, 2)
        straight = round(route["straight_line_m"] / 1000, 2)
        return {"ok": True, "distance_km": km, "straight_line_km": straight,
                "summary": f"road distance {km} km (straight line {straight} km)"}

    def get_weather(self, state: TripState, args: dict) -> dict:
        where = args.get("location", "midpoint")
        if where == "source":
            lat, lon = state.source
        elif where == "destination":
            lat, lon = state.destination
        else:
            where = "midpoint"
            lat, lon = state.midpoint

        state.weather = self.weather_agent.analyze(lat, lon)
        temp, wind = state.weather["avg_temperature"], state.weather["avg_windspeed"]
        if temp is None:
            return {"ok": False, "error": "Weather service returned no data."}
        return {"ok": True, "temperature_c": temp, "wind_kmh": wind,
                "summary": f"{temp} C, wind {wind} km/h at {where}"}

    def check_transport(self, state: TripState, args: dict) -> dict:
        state.transport = self.transport_agent.check_availability(*state.source, *state.destination)
        t = state.transport
        return {"ok": True, "bus_available": t["bus_available"], "metro_available": t["metro_available"],
                "summary": f"bus {'yes' if t['bus_available'] else 'no'}, "
                           f"metro {'yes' if t['metro_available'] else 'no'}"}

    def get_graph_context(self, state: TripState, args: dict) -> dict:
        state.graph_context = self.graph_rag_agent.fetch_context(
            *state.source, *state.destination, transport=state.transport)
        return {"ok": True, "context": state.graph_context["summary"],
                "summary": f"{state.graph_context['weather_points']} stored weather points; stop lookups done"}


def run_tool(toolkit: ToolKit, state: TripState, name: str, raw_args, trace: list,
             actor: str, step: int, seen: set | None = None) -> dict:
    """
    Execute one tool call safely and append a trace row. Never raises: every failure
    (unknown tool, bad JSON, exception inside the tool, repeated call) becomes a result the
    model can read and react to.
    """
    started = time.perf_counter()
    status, args = "ok", {}

    def finish(result: dict) -> dict:
        trace.append({
            "step": step, "actor": actor, "tool": name, "args": args, "status": status,
            "ms": round((time.perf_counter() - started) * 1000),
            "summary": result.get("summary") or result.get("error") or "",
        })
        return result

    tool = toolkit.by_name.get(name)
    if tool is None:
        status = "error"
        return finish({"ok": False, "error": f"Unknown tool '{name}'. Available: {sorted(toolkit.by_name)}"})

    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) and raw_args.strip() else (raw_args or {})
        if not isinstance(args, dict):
            raise ValueError("arguments must be a JSON object")
    except (ValueError, TypeError) as exc:
        args, status = {}, "error"
        return finish({"ok": False, "error": f"Invalid arguments: {exc}"})

    if seen is not None:
        key = (name, json.dumps(args, sort_keys=True))
        if key in seen:
            status = "skipped"
            return finish({"ok": False, "error": "Already called with the same arguments; reuse the earlier result."})
        seen.add(key)

    try:
        result = tool.fn(state, args)
    except Exception as exc:
        status = "error"
        return finish({"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    if not result.get("ok", False):
        status = "error"
    return finish(result)
