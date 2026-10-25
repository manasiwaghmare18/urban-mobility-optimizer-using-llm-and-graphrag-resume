"""Manual check - needs real credentials / network. Run from the project root: python scripts/manual_checks/check_weather_mapping.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from data_ingestion.road_network import (
    fetch_hyderabad_road_network,
    extract_nodes,
    extract_road_segments
)
from data_ingestion.weather_scraper import enrich_roads_with_weather

graph = fetch_hyderabad_road_network()
nodes = extract_nodes(graph)
roads = extract_road_segments(graph)

# Test on small subset (important!)
sample_roads = roads[:20]

enriched = enrich_roads_with_weather(sample_roads, nodes)

print(enriched[0])
