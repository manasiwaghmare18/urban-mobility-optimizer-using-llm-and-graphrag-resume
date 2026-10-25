"""
Rebuild data/metro_stations.csv so it contains ONLY Hyderabad Metro stations.

Why: the original extraction used the OSM filter  railway=station OR station=subway,
which also pulled in Indian Railways / MMTS suburban stops, stations still under
construction ("(u/c)"), disused stations and duplicate nodes of the same station.

Input : the cached Overpass response that the original ingestion run produced
        (data_ingestion/cache/<hash>.json containing the metro query).
Output: data/metro_stations.csv  (original is backed up once to metro_stations.raw.csv)

Usage:  python scripts/clean_metro_stations.py [path/to/overpass_cache.json]
"""
import json
import math
import os
import re
import sys
from glob import glob

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
METRO_NETWORKS = {"hyderabad metro", "hydeabad metro rail"}      # (sic) typo exists in OSM
METRO_OPERATOR_HINT = "hyderabad metro rail"
DEDUPE_RADIUS_M = 300  # same name within this distance = same station (several OSM nodes)


def _is_metro(tags: dict) -> bool:
    network = tags.get("network", "").strip().lower()
    operator = tags.get("operator", "").strip().lower()
    return (
        network in METRO_NETWORKS
        or METRO_OPERATOR_HINT in operator
        or tags.get("station", "").lower() in {"subway", "metro"}
    )


def _is_active(tags: dict) -> bool:
    name = tags.get("name", "")
    if "(u/c)" in name.lower():
        return False
    if tags.get("construction") or tags.get("disused") == "yes" or tags.get("proposed"):
        return False
    return True


def _metres(lat1, lon1, lat2, lon2) -> float:
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 2 * 6371008.8 * math.asin(math.sqrt(a))


def _key(name: str) -> str:
    """Normalise a station name so 'Kukatpally' and 'Kukatpally Metro' collapse to one key.
    Parenthesised text (e.g. '(Red Line)') is kept so interchange stations stay distinct."""
    k = name.lower()
    k = re.sub(r"\b(metro|station|rail)\b", " ", k)
    k = re.sub(r"[^a-z0-9()]+", " ", k)
    return re.sub(r"\s+", " ", k).strip()


def find_metro_cache() -> str:
    """Pick the cached Overpass file that contains the metro-station query."""
    for path in glob(os.path.join(ROOT, "data_ingestion", "cache", "*.json")):
        if os.path.getsize(path) > 5_000_000:
            continue  # the big file is the road network
        try:
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
        except Exception:
            continue
        if not isinstance(doc, dict):
            continue
        tags = [e.get("tags", {}) for e in doc.get("elements", [])]
        if any(t.get("network", "").lower() in METRO_NETWORKS for t in tags):
            return path
    raise FileNotFoundError("No cached Overpass metro response found; pass its path explicitly.")


def main(cache_path: str | None = None):
    cache_path = cache_path or find_metro_cache()
    with open(cache_path, encoding="utf-8") as fh:
        elements = json.load(fh)["elements"]

    rows = []
    for el in elements:
        tags = el.get("tags", {})
        if el.get("type") != "node" or "name" not in tags:
            continue  # ways carry no coordinates in this cache
        if _is_metro(tags) and _is_active(tags):
            rows.append({"name": tags["name"].strip(), "lat": el["lat"], "lon": el["lon"]})

    # Shortest names first so the clean spelling ("Kukatpally") wins over "Kukatpally Metro".
    rows.sort(key=lambda r: (len(r["name"]), r["name"]))
    kept = []
    for row in rows:
        if any(_key(k["name"]) == _key(row["name"])
               and _metres(k["lat"], k["lon"], row["lat"], row["lon"]) < DEDUPE_RADIUS_M for k in kept):
            continue
        kept.append(row)

    df = pd.DataFrame(kept).sort_values("name").reset_index(drop=True)

    out = os.path.join(DATA_DIR, "metro_stations.csv")
    backup = os.path.join(DATA_DIR, "metro_stations.raw.csv")
    if os.path.exists(out) and not os.path.exists(backup):
        os.replace(out, backup)
    df.to_csv(out, index=False)
    print(f"cache      : {cache_path}")
    print(f"candidates : {len(rows)}  ->  after de-duplication: {len(df)}")
    print(f"written    : {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
