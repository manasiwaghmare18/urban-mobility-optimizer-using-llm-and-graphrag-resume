"""Headless Streamlit run (streamlit.testing) - checks the page renders and a full request works."""
import os

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from tests.conftest import FakeConn, ScriptedLLM


def run_app(monkeypatch, llm=None, conn=None):
    import agents.weather_agent as wa
    import graph_db.neo4j_connection as nc
    from llm import llm_client

    monkeypatch.setattr(nc, "Neo4jConnection", lambda: conn or FakeConn())
    monkeypatch.setattr(wa, "fetch_realtime_weather",
                        lambda lat, lon: {"temperature": 27.0, "windspeed": 3.0})
    if llm is not None:
        monkeypatch.setattr(llm_client, "get_client", lambda: llm)
    else:
        monkeypatch.setattr(llm_client, "get_client",
                            lambda: (_ for _ in ()).throw(RuntimeError("no key")))

    app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui", "app.py")
    at = AppTest.from_file(app_path, default_timeout=120)
    at.run()
    return at


def click(at, label):
    next(b for b in at.sidebar.button if b.label.endswith(label)).click()
    return at.run()


def test_page_renders_without_exceptions(monkeypatch):
    at = run_app(monkeypatch)
    assert not at.exception
    assert len(at.sidebar.selectbox[0].options) > 300           # routable stops + metro stations
    assert len(set(at.sidebar.selectbox[0].options)) == len(at.sidebar.selectbox[0].options)  # unique labels


def test_agent_request_end_to_end(monkeypatch):
    llm = ScriptedLLM([[("find_route", {})], [("check_transport", {}), ("get_graph_context", {})],
                       [("get_weather", {})], "DONE"])
    at = run_app(monkeypatch, llm=llm)
    options = at.sidebar.selectbox[0].options
    gachibowli = [o for o in options if "Gachibowli ·" in o]
    assert len(gachibowli) == 3     # three different stops share this name; each is now selectable
    at.sidebar.selectbox[0].select(gachibowli[0])
    at = click(at, "Find Best Route")
    assert not at.exception
    assert at.session_state["result"]["mode"] == "agent"
    assert "error" not in at.session_state["result"]


def test_unavailable_modes_do_not_crash_the_chart(monkeypatch):
    """Regression: float('N/A') used to raise ValueError when bus/metro were unavailable."""
    at = run_app(monkeypatch, conn=FakeConn(bus_m=9000, metro_m=9000))
    at.sidebar.radio[0].set_value("Fixed")
    at = click(at, "Find Best Route")
    assert not at.exception
    result = at.session_state["result"]
    assert result["cost"]["metro_cost_rs"] is None and result["cost"]["bus_cost_rs"] is None


def test_same_source_and_destination_is_rejected(monkeypatch):
    at = run_app(monkeypatch)
    label = at.sidebar.selectbox[0].options[0]
    at.sidebar.selectbox[0].select(label)
    at.sidebar.selectbox[1].select(label)
    at = click(at, "Find Best Route")
    assert any("two different" in w.value for w in at.warning)


def test_weather_button_fetches_before_connecting_to_neo4j(monkeypatch):
    """Regression for 'Failed to read from defunct connection': the slow web calls must finish
    BEFORE any database connection is opened, and the sample must be small."""
    import data_ingestion.weather_sample as ws
    import graph_db.load_data as ld

    events = []

    def fake_fetch(lat, lon):
        events.append("fetch")
        return {"temperature": 30.0, "windspeed": 5.0, "weathercode": 1, "timestamp": "2026-10-22T10:00"}

    def fake_conn():
        events.append("db_open")
        return FakeConn()

    at = run_app(monkeypatch)
    monkeypatch.setattr(ws, "fetch_realtime_weather", fake_fetch)
    monkeypatch.setattr(ld, "Neo4jConnection", fake_conn)

    at = click(at, "Update Live Weather")
    assert not at.exception
    assert any("Live weather stored" in s.value for s in at.success)
    first_db = events.index("db_open")
    assert events[:first_db] == ["fetch"] * first_db and first_db >= 25      # all fetches first
    assert events.count("db_open") == 1                                       # one short-lived connection


def test_new_ui_shows_clean_stop_names_and_answer_cards(monkeypatch):
    """The redesigned page: tidy labels (incl. the 'bustop' typo in the data), recommendation and cards."""
    at = run_app(monkeypatch, conn=FakeConn(bus_m=100, metro_m=9000))
    options = at.sidebar.selectbox[0].options
    assert any(o.endswith("Gachibowli Flyover Bus Stop") for o in options)        # was 'Gachibowli flyover bustop'
    assert not any("bustop" in o for o in options)
    at.sidebar.radio[0].set_value("Fixed")
    at = click(at, "Find Best Route")
    assert not at.exception
    html = " ".join(m.value for m in at.markdown)
    assert "umo-reco" in html and "umo-mode" in html and "RECOMMENDED" in html     # recommendation + cards
    assert "Not available for this trip" in html                                    # metro explained
    assert "umo-trace" not in html or "Fixed code" in html                          # trace uses readable labels


def test_very_short_trip_recommends_walking_not_an_unverified_mode(monkeypatch):
    at = run_app(monkeypatch)
    opts = at.sidebar.selectbox[0].options
    at.sidebar.selectbox[0].select(next(o for o in opts if o.endswith("Ameerpet (Red Line)")))
    at.sidebar.selectbox[1].select(next(o for o in opts if o.startswith("🚌") and o.endswith("Ameerpet")))
    at.sidebar.radio[0].set_value("Fixed")
    at = click(at, "Find Best Route")
    assert not at.exception
    assert at.session_state["result"]["distance_km"] < 1.5
    html = " ".join(m.value for m in at.markdown)
    assert "🚶 Walk" in html and "Short trip" in html          # walking is the headline
    assert "RECOMMENDED" not in html                            # no motorised card is ringed as best


def test_normal_trip_still_recommends_a_mode(monkeypatch):
    at = run_app(monkeypatch)
    at.sidebar.radio[0].set_value("Fixed")
    at = click(at, "Find Best Route")
    html = " ".join(m.value for m in at.markdown)
    assert "RECOMMENDED" in html and "🚶 Walk" not in html
    assert "1 tool calls" not in html


def test_walk_strip_text_reads_correctly():
    from ui import theme
    html = theme.recommendation_walk(9, 0.75)
    assert "a stop, so for trips" in html and "stop,so" not in html
