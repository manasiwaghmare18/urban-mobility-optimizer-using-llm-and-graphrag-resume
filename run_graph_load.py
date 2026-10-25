"""
Load the Hyderabad city graph (CSV -> Neo4j) using batched writes.

    python run_graph_load.py                 # load everything except live weather
    python run_graph_load.py --dry-run       # no database needed: show what WOULD be loaded
    python run_graph_load.py --only roads    # re-run a single stage (locations/roads/bus/metro)
    python run_graph_load.py --with-weather  # also fetch live weather for 500 road segments (slow)

Safe to re-run: every write is a MERGE, so an interrupted load can simply be started again.
"""
import argparse
import os
import sys
import time

import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from graph_db.batch_loader import (  # noqa: E402
    DEFAULT_BATCH_SIZE, BatchGraphLoader, expected_counts,
    prepare_locations, prepare_points, prepare_roads,
)

STAGES = ["locations", "roads", "bus", "metro"]
WEATHER_ROAD_LIMIT = 500


def read(name):
    return pd.read_csv(os.path.join(ROOT, "data", name))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="prepare the data and print counts; do not touch Neo4j")
    parser.add_argument("--only", choices=STAGES, help="run just one stage")
    parser.add_argument("--with-weather", action="store_true", help="also load live weather (500 API calls, slow)")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()

    started = time.time()
    print("Preparing data from CSV ...")
    nodes_df, roads_df = read("nodes.csv"), read("road_segments.csv")
    locations = prepare_locations(nodes_df)
    roads = prepare_roads(nodes_df, roads_df)
    bus = prepare_points(read("bus_stops.csv"), "bus", "Unnamed Bus Stop")
    metro = prepare_points(read("metro_stations.csv"), "metro", "Unnamed Metro Station")
    expected = expected_counts(locations, roads, bus, metro)

    print(f"   CSV road rows: {len(roads_df):,}  ->  unique roads to load: {len(roads):,} "
          "(shortest parallel edge kept, self-loops skipped)")
    for label, count in expected.items():
        print(f"   will create {count:>9,} {label}")

    if args.dry_run:
        print("\nDry run only - nothing was sent to Neo4j.")
        return

    from graph_db.neo4j_connection import Neo4jConnection  # imported late so --dry-run needs no .env

    conn = Neo4jConnection()
    try:
        loader = BatchGraphLoader(conn, batch_size=args.batch_size)
        loader.create_schema()

        plan = {"locations": (loader.load_locations, locations), "roads": (loader.load_roads, roads),
                "bus": (loader.load_bus_stops, bus), "metro": (loader.load_metro_stations, metro)}
        for stage in ([args.only] if args.only else STAGES):
            plan[stage][0](plan[stage][1])

        if args.with_weather:
            from data_ingestion.weather_scraper import enrich_roads_with_weather
            from graph_db.load_data import GraphLoader
            print(f"Fetching live weather for {WEATHER_ROAD_LIMIT} road segments (slow) ...")
            nodes = {int(r.node_id): {"latitude": r.latitude, "longitude": r.longitude}
                     for r in nodes_df.itertuples()}
            enriched = enrich_roads_with_weather(roads_df.to_dict(orient="records")[:WEATHER_ROAD_LIMIT], nodes)
            old_loader = GraphLoader()
            old_loader.load_weather(enriched)
            old_loader.close()

        print("\nVerifying counts in Neo4j ...")
        wanted = expected if not args.only else {
            {"locations": "Location", "roads": "CONNECTS", "bus": "BusStop", "metro": "MetroStation"}[args.only]:
            expected[{"locations": "Location", "roads": "CONNECTS", "bus": "BusStop", "metro": "MetroStation"}[args.only]]}
        problems = loader.verify(wanted)
    finally:
        conn.close()

    minutes = (time.time() - started) / 60
    if problems:
        print(f"\nFinished in {minutes:.1f} min, but counts differ: {problems}\n"
              "Re-run the command (it is safe) and tell me if the mismatch stays.")
        sys.exit(1)
    print(f"\nGraph load complete in {minutes:.1f} min. Everything matches the CSV files.")


if __name__ == "__main__":
    main()
