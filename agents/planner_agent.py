# agents/planner_agent.py
class PlannerAgent:
    """
    Fixed-order plan used by the FIXED PIPELINE mode (and as the fallback when the LLM
    tool-calling agent fails).

    This is intentionally NOT an LLM planner. In "agent" mode the decision of which tools
    to call, and in what order, is made by the LLM in agents/agent_loop.py.
    """

    FIXED_PLAN = ["route", "weather", "transport", "cost", "graph_context", "explanation"]

    def create_plan(self, user_goal: str):
        return list(self.FIXED_PLAN)
