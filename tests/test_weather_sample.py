import os

import pandas as pd

from data_ingestion import weather_sample as ws

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def real_frames():
    return (pd.read_csv(os.path.join(ROOT, "data", "nodes.csv")),
            pd.read_csv(os.path.join(ROOT, "data", "road_segments.csv"), usecols=["from_node", "to_node"]))


def test_sample_is_small_and_spread_across_the_city():
    nodes, roads = real_frames()
    segs = ws.pick_spread_segments(nodes, roads)
    assert 25 <= len(segs) <= 40
    pts = nodes.set_index("node_id").loc[[s["from_node"] for s in segs], ["latitude", "longitude"]]
    lat_span = pts.latitude.max() - pts.latitude.min()
    lon_span = pts.longitude.max() - pts.longitude.min()
    assert lat_span > 0.8 * (nodes.latitude.max() - nodes.latitude.min())     # covers north-south
    assert lon_span > 0.8 * (nodes.longitude.max() - nodes.longitude.min())   # covers east-west
    assert len({(s["from_node"], s["to_node"]) for s in segs}) == len(segs)


def test_parallel_fetch_keeps_order_and_survives_failures():
    nodes = {i: {"latitude": 17.0 + i, "longitude": 78.0} for i in range(1, 7)}
    segs = [{"from_node": i, "to_node": i + 1} for i in range(1, 6)]
    calls = []

    def fake(lat, lon):
        calls.append(lat)
        if lat == 19.5:                         # segment 2-3 fails inside the fetch function
            raise RuntimeError("timeout")
        return {"temperature": lat, "windspeed": 1.0, "weathercode": 0, "timestamp": "t"}

    orig = ws.fetch_realtime_weather
    ws.fetch_realtime_weather = fake
    try:
        out = ws.fetch_weather_parallel(segs, nodes, workers=3)
    finally:
        ws.fetch_realtime_weather = orig

    assert [s["from_node"] for s in out] == [1, 2, 3, 4, 5]          # order preserved
    assert out[1]["weather"] is None and out[0]["weather"]["temperature"] == 18.5
    assert len(calls) == 5


def test_missing_nodes_are_skipped_not_fatal():
    out = ws.fetch_weather_parallel([{"from_node": 1, "to_node": 99}], {1: {"latitude": 1, "longitude": 1}})
    assert out[0]["weather"] is None
