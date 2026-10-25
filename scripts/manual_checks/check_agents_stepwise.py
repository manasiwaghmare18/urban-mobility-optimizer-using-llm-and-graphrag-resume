"""Manual check - needs real credentials / network. Run from the project root: python scripts/manual_checks/check_agents_stepwise.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from graph_db.neo4j_connection import Neo4jConnection
from agents.route_agent import RouteAgent
from agents.weather_agent import WeatherAgent
from agents.cost_agent import CostAgent
from agents.transport_agent import TransportAgent
from agents.graph_rag_agent import GraphRAGAgent

conn = Neo4jConnection()

src = (17.4375, 78.4483)   # Ameerpet
dst = (17.4401, 78.3489)   # Gachibowli

print("\n--- ROUTE AGENT ---")
route = RouteAgent(conn).find_route(*src, *dst)
print(route)

print("\n--- WEATHER AGENT (REAL TIME) ---")
weather = WeatherAgent().analyze(
    lat=(src[0] + dst[0]) / 2,
    lon=(src[1] + dst[1]) / 2
)
print(weather)

print("\n--- COST AGENT ---")
cost = CostAgent().estimate(route["distance_m"])
print(cost)

print("\n--- TRANSPORT AGENT ---")
transport = TransportAgent(conn).check_availability(*src, *dst)
print(transport)

print("\n--- GRAPH RAG AGENT ---")
graph_context = GraphRAGAgent(conn).fetch_context(*src, *dst)
print(graph_context)

conn.close()
