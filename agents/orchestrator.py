# agents/orchestrator.py
from agents.agent_loop import AgentLoop, AgentLoopError
from agents.cost_agent import CostAgent
from agents.graph_rag_agent import GraphRAGAgent
from agents.planner_agent import PlannerAgent
from agents.route_agent import RouteAgent
from agents.tools import ToolKit, TripState, run_tool
from agents.transport_agent import TransportAgent
from agents.weather_agent import WeatherAgent
from config import settings
from llm import llm_client
from llm.prompt_templates import build_trip_facts
from routing.road_graph import haversine_m


class OrchestratorAgent:
    """
    Two modes:

    agent (default) - an LLM decides which tools to call and when to stop (agents/agent_loop.py).
                      Cost estimation and the final explanation are always done afterwards
                      by this class, because they are deterministic, not decisions.
    fixed           - the original fixed-order pipeline (PlannerAgent.FIXED_PLAN).

    If the LLM cannot be used for planning (no key, API error, malformed tool call) the agent
    mode falls back to the fixed pipeline for whatever is still missing and reports why.
    """

    def __init__(self, conn, llm=None, road_graph=None, weather_fetch=None, max_steps=None):
        self.conn = conn
        self.llm = llm                      # injectable OpenAI-compatible client (tests / custom)
        self.max_steps = max_steps or settings.AGENT_MAX_STEPS

        self.planner = PlannerAgent()
        self.route_agent = RouteAgent(conn, road_graph)
        self.weather_agent = WeatherAgent(weather_fetch)
        self.cost_agent = CostAgent()
        self.transport_agent = TransportAgent(conn)
        self.graph_rag_agent = GraphRAGAgent(conn, self.transport_agent)
        self.toolkit = ToolKit(self.route_agent, self.weather_agent,
                               self.transport_agent, self.graph_rag_agent)

    # ----------------------------------------------------------------- helpers
    def _client(self):
        if self.llm is not None:
            return self.llm
        try:
            return llm_client.get_client()
        except RuntimeError:
            return None

    def _run_fixed(self, state, trace, actor):
        """Run every step of the fixed plan that has not produced a result yet."""
        for item in self.planner.create_plan("optimize urban travel"):
            step = len(trace) + 1          # consecutive numbers: 1, 2, 3, ...
            if item == "route" and state.route is None:
                run_tool(self.toolkit, state, "find_route", {}, trace, actor, step)
            elif state.route is None:
                break  # nothing else is meaningful without a route
            elif item == "weather" and state.weather is None:
                run_tool(self.toolkit, state, "get_weather", {}, trace, actor, step)
            elif item == "transport" and state.transport is None:
                run_tool(self.toolkit, state, "check_transport", {}, trace, actor, step)
            elif item == "graph_context" and state.graph_context is None:
                run_tool(self.toolkit, state, "get_graph_context", {}, trace, actor, step)

    # -------------------------------------------------------------------- main
    def handle_request(self, source, destination, labels=None, use_agent=True):
        labels = labels or (None, None)
        state = TripState(tuple(source), tuple(destination), labels[0], labels[1])
        trace, fallback_reason, mode = [], None, "fixed"
        client = self._client()

        if use_agent:
            if client is None:
                fallback_reason = "GROQ_API_KEY is not set, so the LLM could not plan."
                mode = "fixed (agent fallback)"
            else:
                straight_km = haversine_m(*state.source, *state.destination) / 1000
                prompt = (f"Trip: {labels[0] or 'start point'} to {labels[1] or 'destination'}. "
                          f"Straight-line distance is about {straight_km:.1f} km. "
                          "Gather the data needed to compare car, bus and metro.")
                try:
                    loop = AgentLoop(client, llm_client.MODEL_NAME, self.toolkit, self.max_steps)
                    outcome = loop.run(state, prompt, trace)
                    mode = "agent"
                    if not outcome["finished"]:
                        fallback_reason = f"Agent reached the {self.max_steps}-step limit before finishing."
                except AgentLoopError as exc:
                    fallback_reason = str(exc)
                    mode = "fixed (agent fallback)"

            if mode == "agent":
                if state.route is None:          # safety net: a route is mandatory
                    run_tool(self.toolkit, state, "find_route", {}, trace, "pipeline", len(trace) + 1)
                # The agent may skip the transport check only on very short trips. On anything longer,
                # recommending bus/metro without verifying them would be wrong, so we run it ourselves.
                if (state.route is not None and state.transport is None
                        and state.route["distance_m"] / 1000 >= CostAgent.SHORT_TRIP_KM):
                    run_tool(self.toolkit, state, "check_transport", {}, trace, "pipeline", len(trace) + 1)
            else:
                self._run_fixed(state, trace, "pipeline")
        else:
            self._run_fixed(state, trace, "pipeline")

        base = {"mode": mode, "fallback_reason": fallback_reason, "trace": trace,
                "source_label": labels[0], "destination_label": labels[1],
                "source": state.source, "destination": state.destination}

        if state.route is None:
            error = self.route_agent.last_error or "No route found"
            hint = f" {self.route_agent.last_hint}" if self.route_agent.last_hint else ""
            return {**base, "error": error + hint}

        # ----- deterministic finishing steps (not agent decisions)
        t = state.transport
        cost = self.cost_agent.estimate(
            state.route["distance_m"],
            bus_available=True if t is None else t["bus_available"],
            metro_available=True if t is None else t["metro_available"],
        )
        distance_km = round(state.route["distance_m"] / 1000, 2)
        straight_km = round(state.route["straight_line_m"] / 1000, 2)

        facts = build_trip_facts(
            distance_km, cost, weather=state.weather, transport=t, graph_context=state.graph_context,
            straight_line_km=straight_km, source_label=labels[0], destination_label=labels[1],
            walk_min=(self.cost_agent.walk_minutes(state.route["distance_m"])
                      if distance_km < CostAgent.SHORT_TRIP_KM else None),
        )
        explanation = llm_client.explain_trip(facts, client=client)
        trace.append({"step": len(trace) + 1, "actor": "pipeline", "tool": "write_explanation", "args": {},
                      "status": "ok" if explanation["source"] == "llm" else "fallback", "ms": 0,
                      "summary": ("LLM explanation" if explanation["source"] == "llm"
                                  else f"template used ({explanation['error']})")})

        return {
            **base,
            "distance_km": distance_km,
            "straight_line_km": straight_km,
            "weather": state.weather,
            "cost": cost,
            "transport": t,
            "graph_context": state.graph_context,
            "route_path": state.route["path"],
            "route_method": state.route["method"],
            "facts": facts,
            "llm_explanation": explanation["text"],
            "explanation_source": explanation["source"],
            "explanation_error": explanation["error"],
        }
