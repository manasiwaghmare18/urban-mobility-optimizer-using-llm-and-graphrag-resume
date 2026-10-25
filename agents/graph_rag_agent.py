# agents/graph_rag_agent.py
from agents.transport_agent import TransportAgent


class GraphRAGAgent:
    """
    Retrieves facts from the Neo4j city graph and turns them into grounded context text for
    the LLM: nearest bus stop / metro station at both ends of the trip, plus any stored
    weather observations around the route midpoint.

    Only facts actually present in the graph are returned. If the graph has nothing for the
    area, the text says so, and the LLM is told not to invent anything.
    """

    WEATHER_RADIUS_M = 4000   # stored weather is sampled on a ~5 km grid (see data_ingestion/weather_sample.py)

    def __init__(self, conn, transport_agent=None):
        self.conn = conn
        self.transport_agent = transport_agent or TransportAgent(conn)

    def _stored_weather(self, lat, lon):
        query = """
        MATCH (l:Location)-[:HAS_WEATHER]->(w:Weather)
        WHERE point.distance(
            point({latitude:l.lat, longitude:l.lon}),
            point({latitude:$lat, longitude:$lon})
        ) < $radius
        RETURN avg(w.temperature) AS avg_temp,
               avg(w.windspeed) AS avg_wind,
               count(w) AS weather_points
        """
        rows = self.conn.execute(query, {"lat": lat, "lon": lon, "radius": self.WEATHER_RADIUS_M})
        return rows[0] if rows else {"avg_temp": None, "avg_wind": None, "weather_points": 0}

    @staticmethod
    def _stop_line(kind, role, stop):
        if not stop:
            return f"No {kind} found near the {role} in the graph."
        return f"Nearest {kind} to the {role}: {stop['name'] or 'unnamed'} ({stop['distance_m']:.0f} m away)."

    def fetch_context(self, src_lat, src_lon, dst_lat, dst_lon, transport=None):
        """
        Returns {"summary": str, "weather_points": int, ...}.
        `transport` may be passed in to avoid repeating the stop lookups.
        """
        t = transport or self.transport_agent.check_availability(src_lat, src_lon, dst_lat, dst_lon)
        weather = self._stored_weather((src_lat + dst_lat) / 2, (src_lon + dst_lon) / 2)
        points = int(weather.get("weather_points") or 0)

        lines = [
            self._stop_line("bus stop", "start", t.get("bus_near_source")),
            self._stop_line("bus stop", "destination", t.get("bus_near_destination")),
            self._stop_line("metro station", "start", t.get("metro_near_source")),
            self._stop_line("metro station", "destination", t.get("metro_near_destination")),
        ]
        if points and weather.get("avg_temp") is not None:
            lines.append(
                f"Stored graph weather near the route midpoint averages {weather['avg_temp']:.1f} C "
                f"(from {points} road segments)."
            )
        else:
            lines.append("No stored weather observations exist in the graph near the route midpoint.")

        return {
            "summary": " ".join(lines),
            "weather_points": points,
            "stored_avg_temp": weather.get("avg_temp"),
            "stored_avg_wind": weather.get("avg_wind"),
        }
