# graph_db/batch_loader.py
"""
Fast, batched, re-runnable loader for the Neo4j city graph.

The original GraphLoader sent ONE query per node and per road (~500,000 round trips to Aura).
This sends thousands of rows per query with UNWIND, so the whole graph loads in minutes.

Design notes
------------
* Idempotent: everything uses MERGE, so an interrupted load can simply be re-run.
* Same graph as routing/road_graph.py uses: parallel roads between the same two nodes are
  collapsed to the SHORTEST one (the old loader kept whichever came last) and self-loops
  are skipped, so Neo4j and the in-memory router describe the same network.
* Node ids / properties are identical to the old loader (Location.id is a string,
  BusStop.id = bus_<csv row>, MetroStation.id = metro_<csv row>), so the agents' queries
  keep working.
"""
from __future__ import annotations

import time

import pandas as pd

from graph_db.graph_schema import create_constraints

DEFAULT_BATCH_SIZE = 5000
MAX_ATTEMPTS = 3

LOCATION_QUERY = """
UNWIND $rows AS row
MERGE (l:Location {id: row.id})
SET l.lat = row.lat, l.lon = row.lon
"""

ROAD_QUERY = """
UNWIND $rows AS row
MATCH (a:Location {id: row.from_id})
MATCH (b:Location {id: row.to_id})
MERGE (a)-[c:CONNECTS]->(b)
SET c.length = row.length, c.road_type = row.road_type
"""

BUS_QUERY = """
UNWIND $rows AS row
MERGE (b:BusStop {id: row.id})
SET b.name = row.name, b.lat = row.lat, b.lon = row.lon
"""

METRO_QUERY = """
UNWIND $rows AS row
MERGE (m:MetroStation {id: row.id})
SET m.name = row.name, m.lat = row.lat, m.lon = row.lon
"""

COUNT_QUERIES = {
    "Location": "MATCH (n:Location) RETURN count(n) AS n",
    "CONNECTS": "MATCH ()-[c:CONNECTS]->() RETURN count(c) AS n",
    "BusStop": "MATCH (n:BusStop) RETURN count(n) AS n",
    "MetroStation": "MATCH (n:MetroStation) RETURN count(n) AS n",
}


# --------------------------------------------------------------------- data preparation
def prepare_locations(nodes_df: pd.DataFrame) -> list[dict]:
    return [{"id": str(int(r.node_id)), "lat": float(r.latitude), "lon": float(r.longitude)}
            for r in nodes_df.itertuples()]


def prepare_roads(nodes_df: pd.DataFrame, roads_df: pd.DataFrame) -> list[dict]:
    """One row per (from, to) pair: the shortest parallel road; no self-loops; endpoints must exist."""
    valid = set(nodes_df["node_id"].astype("int64"))
    df = roads_df[["from_node", "to_node", "length_meters", "road_type"]].copy()
    df = df[df["from_node"].isin(valid) & df["to_node"].isin(valid) & (df["from_node"] != df["to_node"])]
    df = df.sort_values("length_meters", kind="stable").drop_duplicates(["from_node", "to_node"], keep="first")
    return [{"from_id": str(int(r.from_node)), "to_id": str(int(r.to_node)),
             "length": float(r.length_meters), "road_type": str(r.road_type)}
            for r in df.itertuples()]


def prepare_points(df: pd.DataFrame, prefix: str, default_name: str) -> list[dict]:
    """Ids follow the CSV row number (bus_0, bus_1, ...) exactly like the old loader."""
    rows = []
    for i, r in enumerate(df.to_dict(orient="records")):
        lat, lon = r.get("lat"), r.get("lon")
        if pd.isna(lat) or pd.isna(lon):
            continue
        name = r.get("name")
        rows.append({"id": f"{prefix}_{i}",
                     "name": default_name if pd.isna(name) else str(name).strip(),
                     "lat": float(lat), "lon": float(lon)})
    return rows


def chunks(rows: list, size: int):
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


def expected_counts(locations, roads, bus, metro) -> dict:
    return {"Location": len(locations), "CONNECTS": len(roads),
            "BusStop": len(bus), "MetroStation": len(metro)}


# --------------------------------------------------------------------------- the loader
class BatchGraphLoader:
    def __init__(self, conn, batch_size: int = DEFAULT_BATCH_SIZE, log=print):
        self.conn = conn
        self.batch_size = batch_size
        self.log = log

    def _run(self, query: str, rows: list):
        """Run one batch; retry a couple of times on transient network / server errors."""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return self.conn.execute(query, {"rows": rows})
            except Exception as exc:
                if attempt == MAX_ATTEMPTS:
                    raise
                wait = 3 * attempt
                self.log(f"   batch failed ({type(exc).__name__}); retry {attempt}/{MAX_ATTEMPTS - 1} in {wait}s")
                time.sleep(wait)

    def _load(self, label: str, query: str, rows: list):
        total, started = len(rows), time.time()
        self.log(f"Loading {label}: {total:,} rows in batches of {self.batch_size:,}")
        done, next_mark = 0, 10
        for batch in chunks(rows, self.batch_size):
            self._run(query, batch)
            done += len(batch)
            pct = 100 * done / total if total else 100
            if pct >= next_mark or done == total:       # one progress line per 10 %
                self.log(f"   {label}: {done:,}/{total:,} ({pct:.0f}%)  {time.time() - started:.0f}s elapsed")
                while next_mark <= pct:
                    next_mark += 10

    def create_schema(self):
        self.log("Creating constraints / indexes ...")
        create_constraints(self.conn)

    def load_locations(self, rows): self._load("Location nodes", LOCATION_QUERY, rows)
    def load_roads(self, rows): self._load("CONNECTS roads", ROAD_QUERY, rows)
    def load_bus_stops(self, rows): self._load("BusStop nodes", BUS_QUERY, rows)
    def load_metro_stations(self, rows): self._load("MetroStation nodes", METRO_QUERY, rows)

    def counts(self) -> dict:
        out = {}
        for label, query in COUNT_QUERIES.items():
            rows = self.conn.execute(query)
            out[label] = int(rows[0]["n"]) if rows else 0
        return out

    def verify(self, expected: dict) -> list[str]:
        """Return a list of mismatch descriptions (empty list = everything matches)."""
        actual = self.counts()
        problems = []
        for label, want in expected.items():
            got = actual.get(label)
            self.log(f"   {label:<13} in Neo4j: {got:>9,}   expected: {want:>9,}   "
                     f"{'OK' if got == want else 'MISMATCH'}")
            if got != want:
                problems.append(f"{label}: found {got}, expected {want}")
        return problems
