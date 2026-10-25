import math
import os

import pandas as pd

from routing.road_graph import RoadGraph
from tests.conftest import AMEERPET, CHHOTA_ANJAIAH, GACHIBOWLI, PUBLIC_LIBRARY


def test_screenshot_route_is_about_16_6_km_not_29(road_graph):
    r = road_graph.route(*CHHOTA_ANJAIAH, *PUBLIC_LIBRARY)
    assert r["ok"]
    km = r["distance_m"] / 1000
    assert 15.5 <= km <= 18.0          # true shortest road path is ~16.6 km
    assert km < 20                      # the old hop-based result was ~29 km


def test_ameerpet_gachibowli(road_graph):
    r = road_graph.route(*AMEERPET, *GACHIBOWLI)
    assert r["ok"] and 13.0 <= r["distance_m"] / 1000 <= 14.5   # old code: 15.4-17.0 km


def test_route_is_at_least_straight_line_and_not_absurd(road_graph):
    r = road_graph.route(*CHHOTA_ANJAIAH, *PUBLIC_LIBRARY)
    assert r["distance_m"] >= r["straight_line_m"] * 0.99
    assert r["distance_m"] / r["straight_line_m"] < 2.0


def test_long_routes_no_longer_fail_at_120_hops(road_graph):
    """The two bus stops (inside road coverage) that are farthest apart. The old Cypher
    shortestPath needed ~229 hops for such a trip and its 120-hop cap returned 'No route found'."""
    import numpy as np
    stops = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "bus_stops.csv"))
    stops = stops.dropna(subset=["name"])
    covered = stops[[road_graph.snap(r.lat, r.lon)[1] < 300 for r in stops.itertuples()]]
    lat, lon = np.radians(covered.lat.to_numpy()), np.radians(covered.lon.to_numpy())
    a = (np.sin((lat[:, None] - lat[None]) / 2) ** 2
         + np.cos(lat[:, None]) * np.cos(lat[None]) * np.sin((lon[:, None] - lon[None]) / 2) ** 2)
    i, j = np.unravel_index(np.argmax(a), a.shape)
    far_a, far_b = covered.iloc[i], covered.iloc[j]
    r = road_graph.route(far_a.lat, far_a.lon, far_b.lat, far_b.lon)
    assert r["ok"] and r["distance_m"] > 20_000
    assert len(r["path"]) > 120      # more road segments than the old hop cap allowed


def test_stops_outside_the_road_network_are_rejected_not_snapped_far_away(road_graph):
    # 'AP/TS RTC Bus Stop' lies ~7-10 km outside the downloaded road network
    r = road_graph.route(17.2379774, 78.4285696, *PUBLIC_LIBRARY)
    assert not r["ok"] and "nearest road" in r["error"]


def test_path_starts_and_ends_near_the_points(road_graph):
    r = road_graph.route(*CHHOTA_ANJAIAH, *PUBLIC_LIBRARY)
    first, last = r["path"][0], r["path"][-1]
    assert math.dist(first, CHHOTA_ANJAIAH) < 0.01
    assert math.dist(last, PUBLIC_LIBRARY) < 0.01


def test_point_outside_city_is_rejected_with_hint(road_graph):
    r = road_graph.route(28.61, 77.20, *PUBLIC_LIBRARY)   # Delhi
    assert not r["ok"] and "nearest road" in r["error"] and r["hint"]


def test_tiny_snap_limit_rejects(road_graph):
    r = road_graph.route(*CHHOTA_ANJAIAH, *PUBLIC_LIBRARY, max_snap_m=0.5)
    assert not r["ok"]


def test_same_point_is_zero_distance(road_graph):
    r = road_graph.route(*AMEERPET, *AMEERPET)
    assert r["ok"] and r["distance_m"] == 0.0


# ---- regression tests on a tiny hand-built graph --------------------------------------
def _tiny_graph(tmp_path):
    """
    1 -> 2 (two parallel edges: 100 m and 900 m), 2 -> 3 (50 m), 1 -> 3 (500 m direct, ONE hop),
    3 -> 1 (1000 m). Hop-count routing from 1 to 3 would take the 500 m direct edge;
    distance routing must take 1->2->3 = 150 m.
    """
    pd.DataFrame({"node_id": [1, 2, 3],
                  "latitude": [17.40, 17.41, 17.42],
                  "longitude": [78.40, 78.40, 78.40]}).to_csv(tmp_path / "nodes.csv", index=False)
    pd.DataFrame({"from_node": [1, 1, 2, 1, 3],
                  "to_node": [2, 2, 3, 3, 1],
                  "length_meters": [100.0, 900.0, 50.0, 500.0, 1000.0],
                  "road_type": ["x"] * 5, "oneway": [True] * 5}).to_csv(tmp_path / "road_segments.csv", index=False)
    return RoadGraph(str(tmp_path / "nodes.csv"), str(tmp_path / "road_segments.csv"))


def test_distance_beats_hop_count_and_parallel_edges_use_shortest(tmp_path):
    g = _tiny_graph(tmp_path)
    r = g.route(17.40, 78.40, 17.42, 78.40, max_snap_m=50)
    assert r["ok"] and r["distance_m"] == 150.0      # not 500 (fewest hops), not 950 (long parallel edge)


def test_one_way_direction_is_respected(tmp_path):
    g = _tiny_graph(tmp_path)
    forward = g.route(17.41, 78.40, 17.42, 78.40, max_snap_m=50)    # 2 -> 3 : 50 m
    backward = g.route(17.42, 78.40, 17.41, 78.40, max_snap_m=50)   # 3 -> 1 -> 2 : 1100 m
    assert forward["distance_m"] == 50.0
    assert backward["distance_m"] == 1100.0
