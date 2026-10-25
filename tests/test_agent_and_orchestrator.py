import pytest

from agents.orchestrator import OrchestratorAgent
from llm import llm_client
from tests.conftest import (AMEERPET, CHHOTA_ANJAIAH, GACHIBOWLI, PUBLIC_LIBRARY,
                            FakeConn, ScriptedLLM)

LONG_TRIP = (CHHOTA_ANJAIAH, PUBLIC_LIBRARY)


def make(conn=None, llm=None, road_graph=None, fake_weather=None, **kw):
    return OrchestratorAgent(conn or FakeConn(), llm=llm, road_graph=road_graph,
                             weather_fetch=fake_weather, **kw)


def tools_called(result, actor=None):
    return [t["tool"] for t in result["trace"] if actor is None or t["actor"] == actor]


def test_agent_mode_happy_path(road_graph, fake_weather):
    llm = ScriptedLLM([[("find_route", {})],
                       [("check_transport", {}), ("get_graph_context", {})],
                       [("get_weather", {"location": "midpoint"})],
                       "DONE"])
    r = make(llm=llm, road_graph=road_graph, fake_weather=fake_weather).handle_request(
        *LONG_TRIP, labels=("A", "B"))
    assert r["mode"] == "agent" and r["fallback_reason"] is None
    assert tools_called(r, "agent") == ["find_route", "check_transport", "get_graph_context", "get_weather"]
    assert 15.5 <= r["distance_km"] <= 18.0
    assert r["llm_explanation"] == "EXPLANATION" and r["explanation_source"] == "llm"
    assert r["cost"]["car_cost_rs"] > 0 and r["transport"]["bus_available"] is True
    assert "Fake Bus Stop" in r["graph_context"]["summary"]       # graph facts exist ...
    last_prompt = [q for q in llm.requests if "tools" not in q][-1]["messages"][-1]["content"]
    assert "Fake Bus Stop" in last_prompt                            # ... and reach the LLM prompt


SHORT_TRIP = ((17.4375, 78.4483), (17.4411, 78.4483))      # about 0.4 km apart


def test_agent_may_skip_checks_on_a_very_short_trip(road_graph):
    llm = ScriptedLLM([[("find_route", {})], "DONE"])
    r = make(llm=llm, road_graph=road_graph).handle_request(*SHORT_TRIP)
    assert tools_called(r) == ["find_route", "write_explanation"]
    assert r["transport"] is None and r["weather"] is None
    assert r["facts"]["walk_min"] is not None and r["distance_km"] < 1.5
    prompt = [q for q in llm.requests if "tools" not in q][-1]["messages"][-1]["content"]
    assert "availability not checked" in prompt and "Live weather: not checked" in prompt
    assert "Walking: about" in prompt                        # the explanation is told walking is an option


def test_skipped_transport_check_on_a_normal_trip_is_run_by_the_safety_net(road_graph):
    """An agent that skips check_transport on a 13.75 km trip must not lead to an unverified recommendation."""
    llm = ScriptedLLM([[("find_route", {})], "DONE"])
    r = make(llm=llm, road_graph=road_graph).handle_request(AMEERPET, GACHIBOWLI)
    rows = [(t["actor"], t["tool"]) for t in r["trace"]]
    assert ("pipeline", "check_transport") in rows
    assert r["transport"] is not None and r["facts"]["walk_min"] is None
    prompt = [q for q in llm.requests if "tools" not in q][-1]["messages"][-1]["content"]
    assert "availability not checked" not in prompt


def test_llm_api_failure_falls_back_to_fixed_pipeline(road_graph, fake_weather):
    llm = ScriptedLLM([RuntimeError("boom")])
    r = make(llm=llm, road_graph=road_graph, fake_weather=fake_weather).handle_request(*LONG_TRIP)
    assert r["mode"] == "fixed (agent fallback)" and "LLM call failed" in r["fallback_reason"]
    assert tools_called(r, "pipeline")[:4] == ["find_route", "get_weather", "check_transport", "get_graph_context"]
    assert 15.5 <= r["distance_km"] <= 18.0           # still returns a correct answer


def test_fallback_when_no_api_key(road_graph, fake_weather, monkeypatch):
    monkeypatch.setattr(llm_client, "get_client", lambda: (_ for _ in ()).throw(RuntimeError("no key")))
    r = make(road_graph=road_graph, fake_weather=fake_weather).handle_request(*LONG_TRIP)
    assert r["mode"] == "fixed (agent fallback)" and "GROQ_API_KEY" in r["fallback_reason"]
    assert r["explanation_source"] == "template" and "Groq" not in r["llm_explanation"]


def test_bad_tool_calls_are_handled_and_reported_to_the_model(road_graph):
    llm = ScriptedLLM([[("does_not_exist", {})],
                       [("find_route", "{not json")],
                       [("find_route", {})],
                       [("find_route", {})],            # identical repeat
                       "DONE"])
    r = make(llm=llm, road_graph=road_graph).handle_request(*LONG_TRIP)
    status = [(t["tool"], t["status"]) for t in r["trace"] if t["actor"] == "agent"]
    assert status == [("does_not_exist", "error"), ("find_route", "error"),
                      ("find_route", "ok"), ("find_route", "skipped")]
    # the model was shown the error text on its next turn
    tool_msgs = [m for m in llm.requests[1]["messages"] if m["role"] == "tool"]
    assert "Unknown tool" in tool_msgs[0]["content"]
    assert r["distance_km"] > 0


def test_step_limit_is_enforced_and_route_safety_net_runs(road_graph):
    endless = [[("get_weather", {"location": loc})] for loc in ("source", "destination", "midpoint")] * 3
    llm = ScriptedLLM(endless)
    r = make(llm=llm, road_graph=road_graph, fake_weather=lambda a, b: {"temperature": 1, "windspeed": 1},
             max_steps=3).handle_request(*LONG_TRIP)
    assert "step limit" in r["fallback_reason"]
    assert sum(1 for q in llm.requests if "tools" in q) == 3
    assert "find_route" in tools_called(r, "pipeline")      # mandatory step added by the safety net
    assert r["distance_km"] > 0


def test_unreachable_point_returns_clear_error(road_graph):
    llm = ScriptedLLM([[("find_route", {})], "DONE"])
    r = make(llm=llm, road_graph=road_graph).handle_request((28.61, 77.20), PUBLIC_LIBRARY)
    assert "error" in r and "nearest road" in r["error"]
    assert r["trace"][0]["status"] == "error"


def test_agent_can_retry_find_route_with_larger_snap(road_graph):
    import pandas as pd
    stops = pd.read_csv("data/bus_stops.csv").dropna(subset=["name"])
    near_miss = [(r.lat, r.lon) for r in stops.itertuples()
                 if 1500 < road_graph.snap(r.lat, r.lon)[1] < 4500]
    assert near_miss, "dataset should contain stops 1.5-4.5 km outside the road network"

    llm = ScriptedLLM([[("find_route", {})], [("find_route", {"max_snap_m": 5000})], "DONE"])
    r = make(llm=llm, road_graph=road_graph).handle_request(near_miss[0], PUBLIC_LIBRARY)

    rows = [(t["tool"], t["status"], t["args"]) for t in r["trace"] if t["tool"] == "find_route"]
    assert rows[0][1] == "error"                                  # default 1 km limit rejected it
    assert rows[1] == ("find_route", "ok", {"max_snap_m": 5000})  # the retry succeeded
    assert r["distance_km"] > 0 and "error" not in r


def test_fixed_mode_runs_whole_plan_without_llm_planning(road_graph, fake_weather):
    llm = ScriptedLLM([])
    r = make(llm=llm, road_graph=road_graph, fake_weather=fake_weather).handle_request(
        *LONG_TRIP, use_agent=False)
    assert r["mode"] == "fixed"
    assert tools_called(r, "pipeline")[:4] == ["find_route", "get_weather", "check_transport", "get_graph_context"]
    assert all("tools" not in q for q in llm.requests)    # LLM used only for the explanation


def test_unavailable_public_transport_gives_none_not_na(road_graph, fake_weather):
    r = make(conn=FakeConn(bus_m=9000, metro_m=9000), road_graph=road_graph,
             fake_weather=fake_weather).handle_request(*LONG_TRIP, use_agent=False)
    assert r["cost"]["bus_cost_rs"] is None and r["cost"]["metro_cost_rs"] is None
    assert r["cost"]["car_cost_rs"] > 0
    assert r["transport"]["bus_available"] is False


def test_model_not_found_gives_an_actionable_message(road_graph, fake_weather):
    err = RuntimeError("Error code: 404 - {'error': {'code': 'model_not_found'}}")
    r = make(llm=ScriptedLLM([err]), road_graph=road_graph, fake_weather=fake_weather).handle_request(*LONG_TRIP)
    assert "LLM_MODEL" in r["fallback_reason"] and "gpt-oss-20b" in r["fallback_reason"]
    assert r["distance_km"] > 0                              # still answers


def test_explanation_error_text_is_actionable():
    from types import SimpleNamespace

    def boom(**kw):
        raise RuntimeError("Error code: 404 - {'error': {'code': 'model_not_found'}}")

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=boom)))
    from agents.cost_agent import CostAgent
    from llm.prompt_templates import build_trip_facts
    out = llm_client.explain_trip(build_trip_facts(5, CostAgent().estimate(5000)), client=client)
    assert out["source"] == "template" and "LLM_MODEL" in out["error"]


def test_tool_names_with_a_prefix_are_accepted(road_graph):
    llm = ScriptedLLM([[("functions.find_route", {})], "DONE"])
    r = make(llm=llm, road_graph=road_graph).handle_request(*LONG_TRIP)
    assert [t["tool"] for t in r["trace"] if t["actor"] == "agent"] == ["find_route"]
    assert r["trace"][0]["status"] == "ok"


def test_trace_steps_are_consecutive_in_fixed_pipeline(road_graph, fake_weather):
    r = make(road_graph=road_graph, fake_weather=fake_weather).handle_request(*LONG_TRIP, use_agent=False)
    steps = [t["step"] for t in r["trace"]]
    assert steps == list(range(1, len(steps) + 1))           # was 1, 2, 3, 5, 5


def test_default_model_is_not_the_retired_llama(monkeypatch):
    import importlib

    import config.settings as settings
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    importlib.reload(settings)
    try:
        assert settings.LLM_MODEL == "openai/gpt-oss-20b"
    finally:
        monkeypatch.undo()
        importlib.reload(settings)           # leave the module as the rest of the suite expects it
