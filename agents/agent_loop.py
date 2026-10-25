# agents/agent_loop.py
"""
LLM tool-calling loop: the model decides which tools to call, in what order, and when to stop.

Safety rails (so a small model cannot break the app):
  * hard step limit
  * repeated identical calls are rejected
  * unknown tools / bad JSON arguments / tool exceptions are returned to the model as errors
  * any failure of the LLM API itself raises AgentLoopError, and the orchestrator then falls
    back to the fixed pipeline
"""
from __future__ import annotations

import json

from agents.tools import ToolKit, TripState, run_tool
from llm import llm_client

AGENT_SYSTEM_PROMPT = """You are the planning agent of an urban mobility assistant for Hyderabad.
Your job is to decide which tools to call to collect the facts needed to compare car, bus and metro for the user's trip. You do NOT write the final answer; a separate step does that once you are finished.

Rules:
1. Call find_route first. Nothing else is useful without a route. If it fails and the error includes a hint, you may retry ONCE with a larger max_snap_m.
2. Call check_transport when bus or metro could realistically be used. Skip it only for very short trips (road distance under about 1.5 km).
3. Call get_weather unless the trip is under about 1 km.
4. Call get_graph_context after check_transport whenever you called check_transport.
5. Call each tool at most once (find_route may be retried once).
6. When you have what you need, reply with the single word DONE."""


class AgentLoopError(Exception):
    """The LLM could not be used for planning (API error, malformed tool call, ...)."""


class AgentLoop:
    def __init__(self, client, model: str, toolkit: ToolKit, max_steps: int = 8):
        self.client = client
        self.model = model
        self.toolkit = toolkit
        self.max_steps = max_steps

    def run(self, state: TripState, user_prompt: str, trace: list) -> dict:
        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        specs = self.toolkit.specs()
        seen: set = set()

        for step in range(1, self.max_steps + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model, messages=messages, tools=specs,
                    tool_choice="auto", temperature=0, timeout=45,
                    **llm_client.completion_kwargs(self.model, 2048),
                )
                message = response.choices[0].message
            except Exception as exc:
                raise AgentLoopError(f"LLM call failed at step {step}: {llm_client.describe_error(exc)}") from exc

            calls = getattr(message, "tool_calls", None) or []
            if not calls:
                return {"finished": True, "steps": step, "final_text": (message.content or "").strip()}

            messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [{
                    "id": c.id, "type": "function",
                    "function": {"name": c.function.name, "arguments": c.function.arguments},
                } for c in calls],
            })
            for call in calls:
                # some models prefix tool names (e.g. "functions.find_route"); our names contain no dots
                name = (call.function.name or "").strip().rsplit(".", 1)[-1]
                result = run_tool(self.toolkit, state, name, call.function.arguments,
                                  trace, actor="agent", step=step, seen=seen)
                messages.append({"role": "tool", "tool_call_id": call.id,
                                 "content": json.dumps(result, default=str)})

        return {"finished": False, "steps": self.max_steps, "final_text": ""}
