from agents.cost_agent import CostAgent
from llm.prompt_templates import (build_trip_facts, explanation_prompt, format_facts, recommendation_reason,
                                  template_explanation)


def test_cost_numbers():
    c = CostAgent().estimate(10_000)
    assert c["car_cost_rs"] == 120.0 and c["bus_cost_rs"] == 20.0 and c["metro_cost_rs"] == 30.0
    assert c["car_time_min"] == 24.0


def test_unavailable_modes_are_none_not_na_strings():
    c = CostAgent().estimate(10_000, bus_available=False, metro_available=False)
    assert c["bus_cost_rs"] is None and c["metro_time_min"] is None and c["car_cost_rs"] == 120.0


def test_cheapest_fastest_balanced_computed_in_python():
    f = build_trip_facts(10, CostAgent().estimate(10_000), transport={"bus_available": True})
    assert f["cheapest"] == "Bus" and f["fastest"] == "Metro"
    assert f["balanced"] in {"Bus", "Metro"}


def test_only_available_modes_are_ranked():
    f = build_trip_facts(10, CostAgent().estimate(10_000, False, False), transport={})
    assert f["options"].keys() == {"Car"} and f["cheapest"] == f["fastest"] == f["balanced"] == "Car"


def test_unchecked_items_are_labelled_not_invented():
    f = build_trip_facts(10, CostAgent().estimate(10_000))
    text = format_facts(f)
    assert "availability not checked" in text and "Live weather: not checked" in text
    assert "not retrieved" in text


def test_template_explanation_has_no_error_text():
    f = build_trip_facts(10, CostAgent().estimate(10_000, True, False), transport={})
    out = template_explanation(f)
    assert "Groq" not in out and "Metro" in out


def test_walking_minutes():
    assert CostAgent().walk_minutes(750) == 9 and CostAgent().walk_minutes(5000) == 60


def test_short_trip_facts_and_template_mention_walking():
    f = build_trip_facts(0.75, CostAgent().estimate(750), walk_min=9)
    assert "Walking: about 9 min" in format_facts(f)
    assert "walking takes about 9 min" in template_explanation(f)


def test_unverified_public_transport_is_flagged_in_the_reason():
    unchecked = build_trip_facts(5, CostAgent().estimate(5000))
    assert unchecked["balanced"] != "Car" and "availability was not checked" in recommendation_reason(unchecked)
    checked = build_trip_facts(5, CostAgent().estimate(5000), transport={"bus_available": True})
    assert "not checked" not in recommendation_reason(checked)


def test_prompt_tells_the_model_to_drop_an_empty_conditions_bullet():
    text = explanation_prompt(build_trip_facts(5, CostAgent().estimate(5000)))
    assert "Leave this bullet out completely" in text and "(none provided)" not in text
