# config/settings.py
"""
Central configuration. Secrets are read from environment variables ONLY.

Local development : copy .env.example to .env and fill in the values (.env is git-ignored).
Streamlit Cloud   : add the same names under  App settings -> Secrets  (they are exposed
                    to the app as environment variables).
"""
import os

from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE") or "neo4j"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "8"))


def require_neo4j_settings() -> None:
    """Raise a readable error instead of failing deep inside the Neo4j driver."""
    missing = [
        name for name, value in (
            ("NEO4J_URI", NEO4J_URI),
            ("NEO4J_USERNAME", NEO4J_USERNAME),
            ("NEO4J_PASSWORD", NEO4J_PASSWORD),
        ) if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing Neo4j settings: " + ", ".join(missing)
            + ". Set them in .env (local) or in Streamlit Secrets (cloud)."
        )
