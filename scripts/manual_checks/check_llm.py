"""
Diagnose the Groq connection in isolation. Run from the project root:
    python scripts/manual_checks/check_llm.py
Prints the model, whether text came back, why generation stopped, and token usage.
It never prints your API key.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from llm import llm_client  # noqa: E402


def show(title, response):
    choice = response.choices[0]
    msg = choice.message
    usage = getattr(response, "usage", None)
    print(f"\n--- {title} ---")
    print("finish_reason     :", getattr(choice, "finish_reason", None))
    print("content length    :", len(msg.content or ""))
    print("tool calls        :", [c.function.name for c in (getattr(msg, "tool_calls", None) or [])])
    print("has reasoning     :", bool(getattr(msg, "reasoning", None)))
    if usage:
        print("completion tokens :", getattr(usage, "completion_tokens", None))
        print("total tokens      :", getattr(usage, "total_tokens", None))
    if msg.content:
        print("first 200 chars   :", msg.content[:200].replace("\n", " "))


def main():
    client = llm_client.get_client()
    model = llm_client.MODEL_NAME
    print("model:", model)

    show("1) plain answer, DEFAULT limits (what failed before)", client.chat.completions.create(
        model=model, temperature=0.3,
        messages=[{"role": "user", "content": "In 60 words, compare bus and car for a 14 km city trip."}]))

    show("2) plain answer, FIXED limits (what the app now sends)", client.chat.completions.create(
        model=model, temperature=0.3,
        messages=[{"role": "user", "content": "In 60 words, compare bus and car for a 14 km city trip."}],
        **llm_client.completion_kwargs(model, 4096)))


if __name__ == "__main__":
    main()
