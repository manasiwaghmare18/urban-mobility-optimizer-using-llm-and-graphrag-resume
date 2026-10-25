# llm/llm_client.py
import os

from openai import OpenAI

from config import settings
from llm.prompt_templates import (
    SYSTEM_PROMPT,
    build_trip_facts,
    explanation_prompt,
    template_explanation,
    walk_recommendation,
)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MODEL_NAME = settings.LLM_MODEL

_client = None


def get_client():
    """Create the Groq client lazily so importing this module never fails without a key."""
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY") or settings.GROQ_API_KEY
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set.")
        _client = OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
    return _client


def completion_kwargs(model: str, max_tokens: int, effort: str = "low") -> dict:
    """
    Extra request options. GPT-OSS is a REASONING model: its hidden thinking tokens count against
    max_completion_tokens (Groq's default is only 1024), so a long think can leave nothing for
    the visible answer. We give it a bigger budget and ask for low reasoning effort.
    Other models do not understand reasoning_effort, so it is only sent to gpt-oss.
    """
    kwargs = {"max_completion_tokens": max_tokens}
    if "gpt-oss" in (model or "").lower():
        kwargs["extra_body"] = {"reasoning_effort": effort}
    return kwargs


def describe_error(exc: Exception) -> str:
    """Turn raw API errors into something a human can act on."""
    text = str(exc)
    if "model_not_found" in text or "does not exist or you do not have access" in text:
        return (f"The model '{MODEL_NAME}' is not available on your Groq account. Set LLM_MODEL in .env "
                f"(or Streamlit Secrets) to a current model such as openai/gpt-oss-20b. Details: {text}")
    if "401" in text or "invalid_api_key" in text:
        return f"Groq rejected the API key - check GROQ_API_KEY. Details: {text}"
    return text


# (token budget, reasoning effort) tried in order if the answer comes back empty
EXPLANATION_ATTEMPTS = [(4096, "low"), (8192, "low")]


def explain_trip(facts: dict, client=None, model: str | None = None) -> dict:
    """
    Returns {"text": str, "source": "llm" | "template", "error": str | None}.
    Falls back to a deterministic template (no invented content) if the LLM call fails or
    keeps returning an empty answer.
    """
    model = model or MODEL_NAME
    try:
        client = client or get_client()
        reason = "empty LLM response"
        for max_tokens, effort in EXPLANATION_ATTEMPTS:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": explanation_prompt(facts)},
                ],
                temperature=0.3,
                timeout=45,
                **completion_kwargs(model, max_tokens, effort),
            )
            choice = response.choices[0]
            text = (choice.message.content or "").strip()
            if text:
                if facts.get("walk_min") is not None:        # very short trip: the app writes the recommendation
                    text = walk_recommendation(facts) + "\n\n" + text
                return {"text": text, "source": "llm", "error": None}
            reason = f"empty LLM response (finish_reason={getattr(choice, 'finish_reason', None)})"
        raise ValueError(reason)
    except Exception as exc:  # network, auth, rate limit, empty answer ...
        return {"text": template_explanation(facts), "source": "template", "error": describe_error(exc)}


def generate_explanation(route, weather, cost, transport, graph_context=None):
    """Backward-compatible wrapper (returns just the text)."""
    facts = build_trip_facts(
        distance_km=route["distance_km"], cost=cost, weather=weather,
        transport=transport, graph_context=graph_context,
    )
    return explain_trip(facts)["text"]
