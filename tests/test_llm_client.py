from types import SimpleNamespace

from agents.cost_agent import CostAgent
from llm import llm_client
from llm.prompt_templates import build_trip_facts

FACTS = build_trip_facts(5, CostAgent().estimate(5000))


def reply(text, finish="stop"):
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish,
                                                    message=SimpleNamespace(content=text, tool_calls=None))])


class Client:
    def __init__(self, replies):
        self.replies, self.requests = list(replies), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.requests.append(kw)
        return self.replies.pop(0)


def test_gpt_oss_gets_bigger_budget_and_low_reasoning():
    kw = llm_client.completion_kwargs("openai/gpt-oss-20b", 4096)
    assert kw == {"max_completion_tokens": 4096, "extra_body": {"reasoning_effort": "low"}}


def test_other_models_do_not_get_reasoning_effort():
    assert "extra_body" not in llm_client.completion_kwargs("some/other-model", 4096)


def test_empty_answer_is_retried_with_a_bigger_budget():
    c = Client([reply("", "length"), reply("Take the bus.")])
    out = llm_client.explain_trip(FACTS, client=c, model="openai/gpt-oss-20b")
    assert out["source"] == "llm" and out["text"] == "Take the bus."
    assert [r["max_completion_tokens"] for r in c.requests] == [4096, 8192]


def test_two_empty_answers_fall_back_and_report_why():
    c = Client([reply("", "length"), reply(None, "length")])
    out = llm_client.explain_trip(FACTS, client=c, model="openai/gpt-oss-20b")
    assert out["source"] == "template" and "finish_reason=length" in out["error"]
    assert "Recommendation" in out["text"]


def test_first_good_answer_needs_only_one_call():
    c = Client([reply("Fine.")])
    assert llm_client.explain_trip(FACTS, client=c, model="openai/gpt-oss-20b")["source"] == "llm"
    assert len(c.requests) == 1


def test_very_short_trip_recommendation_is_written_by_the_app_not_the_model():
    facts = build_trip_facts(0.75, CostAgent().estimate(750), walk_min=9)
    c = Client([reply("- **If you ride:** Bus is cheapest at Rs 1.49.\n*Figures are estimates.*")])
    out = llm_client.explain_trip(facts, client=c, model="openai/gpt-oss-20b")
    assert out["source"] == "llm"
    assert out["text"].startswith("**Recommendation:** This is a very short trip - walking takes about 9 min.")
    assert "If you ride" in out["text"] and out["text"].count("Recommendation") == 1
    prompt = c.requests[0]["messages"][-1]["content"]
    assert "do NOT write a recommendation line" in prompt and "Most balanced" not in prompt


def test_short_trip_template_has_a_ride_line_and_flags_unchecked_availability():
    from llm.prompt_templates import template_explanation
    text = template_explanation(build_trip_facts(0.75, CostAgent().estimate(750), walk_min=9))
    assert "walking takes about 9 min" in text and "If you ride" in text
    assert "availability was not checked" in text and "Most balanced" not in text
