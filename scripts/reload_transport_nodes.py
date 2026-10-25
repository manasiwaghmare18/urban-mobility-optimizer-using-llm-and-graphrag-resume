"""
Replace the MetroStation nodes in Neo4j with the cleaned data/metro_stations.csv.

Run this ONCE after scripts/clean_metro_stations.py. It deletes existing MetroStation nodes first,
because the loader names nodes metro_<row number>: loading a shorter CSV over the old nodes would
leave stale stations behind.

Usage:  python scripts/reload_transport_nodes.py --yes
"""
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from graph_db.load_data import GraphLoader  # noqa: E402
from graph_db.neo4j_connection import Neo4jConnection  # noqa: E402


def main():
    if "--yes" not in sys.argv:
        print("This deletes all MetroStation nodes in the connected Neo4j database and reloads them.\n"
              "Re-run with --yes to continue.")
        return

    stations = pd.read_csv(os.path.join(ROOT, "data", "metro_stations.csv")).to_dict(orient="records")

    conn = Neo4jConnection()
    before = conn.execute("MATCH (m:MetroStation) RETURN count(m) AS n")[0]["n"]
    conn.execute("MATCH (m:MetroStation) DETACH DELETE m")
    conn.close()

    loader = GraphLoader()
    loader.load_metro_stations(stations)
    loader.close()

    conn = Neo4jConnection()
    after = conn.execute("MATCH (m:MetroStation) RETURN count(m) AS n")[0]["n"]
    conn.close()
    print(f"MetroStation nodes: {before} -> {after}  (CSV rows: {len(stations)})")


if __name__ == "__main__":
    main()
