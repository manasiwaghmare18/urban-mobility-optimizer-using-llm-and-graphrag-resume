import os

import pandas as pd
import pytest

from graph_db import batch_loader as bl
from graph_db.batch_loader import BatchGraphLoader, chunks, prepare_points, prepare_roads

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Recorder:
    def __init__(self, counts=None, fail_times=0):
        self.calls, self.counts, self.fail_times = [], counts or {}, fail_times

    def execute(self, query, params=None):
        if "RETURN count(" in query:
            label = next(k for k, q in bl.COUNT_QUERIES.items() if q == query)
            return [{"n": self.counts.get(label, 0)}]
        if self.fail_times:
            self.fail_times -= 1
            raise ConnectionError("temporary")
        self.calls.append((query, params))
        return []


def test_chunks_sizes():
    assert [len(c) for c in chunks(list(range(2500)), 1000)] == [1000, 1000, 500]


def test_loader_sends_batches_with_unwind():
    rec = Recorder()
    rows = [{"id": str(i), "lat": 1.0, "lon": 2.0} for i in range(2500)]
    BatchGraphLoader(rec, batch_size=1000, log=lambda *_: None).load_locations(rows)
    assert [len(p["rows"]) for _, p in rec.calls] == [1000, 1000, 500]
    assert all("UNWIND $rows" in q and "MERGE (l:Location" in q for q, _ in rec.calls)


def test_retry_then_success(monkeypatch):
    monkeypatch.setattr(bl.time, "sleep", lambda s: None)
    rec = Recorder(fail_times=2)
    BatchGraphLoader(rec, log=lambda *_: None).load_bus_stops([{"id": "bus_0", "name": "x", "lat": 1, "lon": 2}])
    assert len(rec.calls) == 1


def test_gives_up_after_three_failures(monkeypatch):
    monkeypatch.setattr(bl.time, "sleep", lambda s: None)
    with pytest.raises(ConnectionError):
        BatchGraphLoader(Recorder(fail_times=5), log=lambda *_: None).load_bus_stops([{"id": "b"}])


def test_prepare_roads_keeps_shortest_parallel_edge_and_drops_bad_rows():
    nodes = pd.DataFrame({"node_id": [1, 2, 3], "latitude": [0, 0, 0], "longitude": [0, 0, 0]})
    roads = pd.DataFrame({"from_node": [1, 1, 2, 2, 9], "to_node": [2, 2, 3, 2, 3],
                          "length_meters": [900.0, 100.0, 50.0, 5.0, 7.0],
                          "road_type": ["a", "b", "c", "loop", "ghost"]})
    out = prepare_roads(nodes, roads)
    assert {(r["from_id"], r["to_id"]): (r["length"], r["road_type"]) for r in out} == {
        ("1", "2"): (100.0, "b"), ("2", "3"): (50.0, "c")}      # parallel -> shortest; loop & ghost dropped


def test_prepare_points_ids_follow_csv_row_and_unnamed_get_default():
    df = pd.DataFrame({"name": ["A", None, "C"], "lat": [1.0, 2.0, None], "lon": [1.0, 2.0, 3.0]})
    out = prepare_points(df, "bus", "Unnamed Bus Stop")
    assert [(r["id"], r["name"]) for r in out] == [("bus_0", "A"), ("bus_1", "Unnamed Bus Stop")]


def test_verify_reports_mismatches():
    rec = Recorder(counts={"Location": 10, "CONNECTS": 5})
    problems = BatchGraphLoader(rec, log=lambda *_: None).verify({"Location": 10, "CONNECTS": 6})
    assert problems == ["CONNECTS: found 5, expected 6"]


def test_real_data_neo4j_graph_matches_the_routing_graph(road_graph):
    """The roads we would load into Neo4j == the edges the Dijkstra router uses."""
    nodes = pd.read_csv(os.path.join(ROOT, "data", "nodes.csv"))
    roads = pd.read_csv(os.path.join(ROOT, "data", "road_segments.csv"))
    assert len(prepare_roads(nodes, roads)) == road_graph.n_edges
    assert len(bl.prepare_locations(nodes)) == road_graph.n_nodes
