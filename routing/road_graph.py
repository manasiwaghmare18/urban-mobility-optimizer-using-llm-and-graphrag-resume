# routing/road_graph.py
"""
In-memory road network with true distance-weighted shortest paths.

Why this exists
---------------
The previous RouteAgent used Neo4j's shortestPath(), which minimises the NUMBER OF
HOPS (road segments), not distance, and was capped at 120 hops. On the Hyderabad
network (avg segment ~57 m) that caps routes at roughly 7 km of dense street grid, and
it prefers paths made of a few very long segments (ring roads), so reported distances
were often far too long (e.g. 29 km for a ~16.6 km trip) or "No route found".

This module loads the same data/nodes.csv + data/road_segments.csv that were used to
build the Neo4j graph and runs Dijkstra on edge length (scipy sparse CSR, ~50 MB RAM).

Behaviour notes
---------------
* Directed: one-way streets are respected (as in the Neo4j graph).
* Parallel edges between the same two nodes are collapsed to the SHORTEST one
  (Neo4j MERGE kept whichever loaded last).
* Start/end points are snapped only onto the largest strongly-connected component, so
  a point can never be snapped onto an isolated road fragment with no route out.
"""
from __future__ import annotations

import math
import os
from functools import lru_cache

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree

EARTH_RADIUS_M = 6_371_008.8
DEFAULT_MAX_SNAP_M = 1000.0
MAX_PATH_POINTS = 600  # keeps the UI map light; the full path is still used for distance


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


class RoadGraph:
    def __init__(self, nodes_csv: str, segments_csv: str):
        nodes = pd.read_csv(nodes_csv, usecols=["node_id", "latitude", "longitude"])
        segs = pd.read_csv(segments_csv, usecols=["from_node", "to_node", "length_meters"])

        self.node_ids = nodes["node_id"].to_numpy(dtype=np.int64)
        self.lat = nodes["latitude"].to_numpy(dtype=float)
        self.lon = nodes["longitude"].to_numpy(dtype=float)
        n = len(nodes)

        index = pd.Index(self.node_ids)
        u = index.get_indexer(segs["from_node"])
        v = index.get_indexer(segs["to_node"])
        w = np.maximum(segs["length_meters"].to_numpy(dtype=float), 0.01)
        keep = (u >= 0) & (v >= 0) & (u != v)

        edges = pd.DataFrame({"u": u[keep], "v": v[keep], "w": w[keep]})
        edges = edges.groupby(["u", "v"], as_index=False)["w"].min()   # shortest parallel edge
        self.n_edges = len(edges)
        self.graph = csr_matrix((edges["w"], (edges["u"], edges["v"])), shape=(n, n))

        # Only snap onto the largest strongly connected component (guarantees a route exists).
        _, labels = connected_components(self.graph, directed=True, connection="strong")
        largest = np.bincount(labels).argmax()
        self.routable = np.flatnonzero(labels == largest)

        # Equirectangular projection (error < 0.1 % at city scale) for the KD-tree.
        self._lat0 = float(np.mean(self.lat))
        self._tree = cKDTree(self._project(self.lat[self.routable], self.lon[self.routable]))

    # ------------------------------------------------------------------ helpers
    def _project(self, lat, lon) -> np.ndarray:
        lat = np.atleast_1d(np.asarray(lat, dtype=float))
        lon = np.atleast_1d(np.asarray(lon, dtype=float))
        x = np.radians(lon) * math.cos(math.radians(self._lat0)) * EARTH_RADIUS_M
        y = np.radians(lat) * EARTH_RADIUS_M
        return np.column_stack([x, y])

    @property
    def n_nodes(self) -> int:
        return len(self.node_ids)

    def snap(self, lat: float, lon: float) -> tuple[int, float]:
        """Nearest routable node index and the straight-line distance to it (metres)."""
        dist, pos = self._tree.query(self._project(lat, lon)[0])
        node = int(self.routable[pos])
        return node, haversine_m(lat, lon, self.lat[node], self.lon[node])

    def _path_points(self, pred: np.ndarray, source: int, target: int) -> list[list[float]]:
        nodes = [target]
        while nodes[-1] != source:
            parent = int(pred[nodes[-1]])
            if parent < 0:
                break
            nodes.append(parent)
        nodes.reverse()
        if len(nodes) > MAX_PATH_POINTS:  # thin out for display only
            step = math.ceil(len(nodes) / MAX_PATH_POINTS)
            nodes = nodes[::step] + ([nodes[-1]] if nodes[-1] != nodes[::step][-1] else [])
        return [[float(self.lat[i]), float(self.lon[i])] for i in nodes]

    # --------------------------------------------------------------------- API
    def route(self, src_lat: float, src_lon: float, dst_lat: float, dst_lon: float,
              max_snap_m: float = DEFAULT_MAX_SNAP_M) -> dict:
        straight = haversine_m(src_lat, src_lon, dst_lat, dst_lon)
        s, snap_s = self.snap(src_lat, src_lon)
        t, snap_t = self.snap(dst_lat, dst_lon)

        for label, snap in (("start", snap_s), ("end", snap_t)):
            if snap > max_snap_m:
                return {
                    "ok": False,
                    "error": (f"The {label} point is {snap:,.0f} m from the nearest road, "
                              f"which is more than the allowed {max_snap_m:,.0f} m."),
                    "hint": "Retry with a larger max_snap_m, or choose a location inside Hyderabad.",
                    "snap_start_m": round(snap_s, 1), "snap_end_m": round(snap_t, 1),
                }

        if s == t:
            return {"ok": True, "distance_m": 0.0, "straight_line_m": straight,
                    "snap_start_m": snap_s, "snap_end_m": snap_t,
                    "path": [[float(self.lat[s]), float(self.lon[s])]],
                    "method": "dijkstra", "n_path_nodes": 1}

        dist, pred = dijkstra(self.graph, directed=True, indices=s, return_predecessors=True)
        d = float(dist[t])
        if not math.isfinite(d):
            return {"ok": False, "error": "No drivable path exists between these two points.",
                    "hint": "The points may be separated by one-way restrictions or data gaps."}

        return {
            "ok": True,
            "distance_m": d,
            "straight_line_m": straight,
            "snap_start_m": snap_s,
            "snap_end_m": snap_t,
            "path": self._path_points(pred, s, t),
            "method": "dijkstra",
        }


def default_data_dir() -> str:
    env = os.getenv("ROAD_DATA_DIR")
    if env:
        return env
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


@lru_cache(maxsize=1)
def get_road_graph(data_dir: str | None = None) -> RoadGraph:
    data_dir = data_dir or default_data_dir()
    return RoadGraph(os.path.join(data_dir, "nodes.csv"),
                     os.path.join(data_dir, "road_segments.csv"))
