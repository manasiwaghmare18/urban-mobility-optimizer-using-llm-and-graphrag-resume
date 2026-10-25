# data_ingestion/weather_sample.py
"""
Helpers for the "Update Live Weather" button.

Problems with the old approach (ui/app.py):
  * it opened Neo4j connections FIRST, then made 100 sequential web calls (minutes, with
    Open-Meteo timeouts), so Aura closed the idle connection ("defunct connection") before the write;
  * it downloaded all 137k Location nodes just to look up 100 coordinates;
  * the 100 segments were simply the first 100 in the database - neighbours of each other - so most
    routes in the city had no stored weather nearby.

Now: choose segments spread over the city from the local CSV files, fetch weather in parallel
without any database connection, and let the caller open Neo4j only for the final write.
"""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from data_ingestion.weather_scraper import fetch_realtime_weather


def pick_spread_segments(nodes_df: pd.DataFrame, roads_df: pd.DataFrame,
                         cell_km: float = 5.0, max_segments: int = 40) -> list[dict]:
    """One road segment per ~cell_km x cell_km grid cell, evenly thinned to max_segments."""
    nodes = nodes_df.set_index("node_id")[["latitude", "longitude"]]
    roads = roads_df[["from_node", "to_node"]].copy()
    roads = roads[roads["from_node"].isin(nodes.index) & roads["to_node"].isin(nodes.index)
                  & (roads["from_node"] != roads["to_node"])]

    lat = nodes["latitude"].reindex(roads["from_node"]).to_numpy()
    lon = nodes["longitude"].reindex(roads["from_node"]).to_numpy()
    lat_step = cell_km / 111.0
    lon_step = cell_km / (111.0 * math.cos(math.radians(float(np.mean(lat)))))
    roads["cell_r"] = np.floor(lat / lat_step).astype(int)
    roads["cell_c"] = np.floor(lon / lon_step).astype(int)

    firsts = roads.drop_duplicates(["cell_r", "cell_c"]).sort_values(["cell_r", "cell_c"])
    if len(firsts) > max_segments:                      # thin evenly so coverage stays city-wide
        keep = np.linspace(0, len(firsts) - 1, max_segments).round().astype(int)
        firsts = firsts.iloc[keep]

    return [{"from_node": int(r.from_node), "to_node": int(r.to_node)} for r in firsts.itertuples()]


def _midpoint(segment: dict, nodes: dict) -> tuple[float, float] | None:
    a, b = nodes.get(segment["from_node"]), nodes.get(segment["to_node"])
    if not a or not b:
        return None
    return (a["latitude"] + b["latitude"]) / 2, (a["longitude"] + b["longitude"]) / 2


def fetch_weather_parallel(segments: list[dict], nodes: dict, workers: int = 5) -> list[dict]:
    """
    Add segment['weather'] (a dict, or None if the API failed) to each segment, keeping the order.
    `nodes` maps node_id -> {"latitude", "longitude"}. Never touches Neo4j.
    """
    def one(segment):
        mid = _midpoint(segment, nodes)
        if mid is None:
            return None
        try:
            return fetch_realtime_weather(*mid)
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(one, segments))
    return [{**seg, "weather": weather} for seg, weather in zip(segments, results)]
