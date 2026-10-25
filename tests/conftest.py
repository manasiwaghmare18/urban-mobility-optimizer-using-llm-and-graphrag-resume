import json
import os
import sys
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Real bus stops used in the project screenshot (distance verified independently with Dijkstra)
CHHOTA_ANJAIAH = (17.447327, 78.363474)
PUBLIC_LIBRARY = (17.373860, 78.477984)
AMEERPET = (17.4375, 78.4483)
GACHIBOWLI = (17.4401, 78.3489)


class FakeConn:
    """Stands in for Neo4jConnection. Answers the queries our agents issue."""

    def __init__(self, bus_m=120.0, metro_m=400.0, weather_points=3, bus_by_call=None):
        self.bus_m, self.metro_m, self.weather_points = bus_m, metro_m, weather_points
        self.bus_by_call = list(bus_by_call or [])
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append(query)
        if "BusStop" in query:
            d = self.bus_by_call.pop(0) if self.bus_by_call else self.bus_m
            return [{"name": "Fake Bus Stop", "distance_m": d}]
        if "MetroStation" in query:
            return [{"name": "Fake Metro", "distance_m": self.metro_m}]
        if "HAS_WEATHER" in query:
            if not self.weather_points:
                return [{"avg_temp": None, "avg_wind": None, "weather_points": 0}]
            return [{"avg_temp": 28.0, "avg_wind": 4.0, "weather_points": self.weather_points}]
        return []

    def close(self):
        pass


class ScriptedLLM:
    """
    Fake OpenAI-compatible client.
    steps: list whose items are
        - list of (tool_name, args)  -> the model calls those tools
        - str                        -> the model answers with text (no tool call)
        - Exception                  -> the API call raises
    Calls without `tools` (the explanation step) always get the text EXPLANATION.
    """

    def __init__(self, steps):
        self.steps = list(steps)
        self.requests = []
        self.n = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.requests.append(kw)
        if "tools" not in kw:
            return self._reply("EXPLANATION")
        step = self.steps.pop(0) if self.steps else "DONE"
        if isinstance(step, Exception):
            raise step
        if isinstance(step, str):
            return self._reply(step)
        calls = []
        for name, args in step:
            self.n += 1
            raw = args if isinstance(args, str) else json.dumps(args)
            calls.append(SimpleNamespace(id=f"call_{self.n}",
                                         function=SimpleNamespace(name=name, arguments=raw)))
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=None, tool_calls=calls))])

    @staticmethod
    def _reply(text):
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=text, tool_calls=None))])


@pytest.fixture(scope="session")
def road_graph():
    from routing.road_graph import get_road_graph
    return get_road_graph()


@pytest.fixture
def fake_weather():
    return lambda lat, lon: {"temperature": 27.0, "windspeed": 3.0, "weathercode": 1, "timestamp": "t"}
