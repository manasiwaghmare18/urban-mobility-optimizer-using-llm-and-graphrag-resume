# agents/transport_agent.py
class TransportAgent:
    """
    Checks whether public transport is usable for a trip by finding the NEAREST bus stop and
    metro station to BOTH the start and the end point (via the Neo4j graph).

    A mode counts as available only if a stop is within its radius at both ends. The old
    version returned True if a stop was near either end, which overstated availability.
    """

    BUS_RADIUS_M = 1000
    METRO_RADIUS_M = 1500
    _LABELS = {"BusStop", "MetroStation"}

    def __init__(self, conn):
        self.conn = conn

    def nearest(self, label, lat, lon):
        """Nearest node with this label to the point: {'name', 'distance_m'} or None."""
        if label not in self._LABELS:  # label is interpolated into Cypher, so whitelist it
            raise ValueError(f"Unsupported label: {label}")

        query = f"""
        MATCH (n:{label})
        WITH n, point.distance(
            point({{latitude: n.lat, longitude: n.lon}}),
            point({{latitude: $lat, longitude: $lon}})
        ) AS distance_m
        ORDER BY distance_m ASC
        LIMIT 1
        RETURN n.name AS name, distance_m
        """
        rows = self.conn.execute(query, {"lat": float(lat), "lon": float(lon)})
        if not rows:
            return None
        row = rows[0]
        return {"name": row.get("name"), "distance_m": round(float(row["distance_m"]), 1)}

    def check_availability(self, src_lat, src_lon, dst_lat, dst_lon):
        bus_src = self.nearest("BusStop", src_lat, src_lon)
        bus_dst = self.nearest("BusStop", dst_lat, dst_lon)
        metro_src = self.nearest("MetroStation", src_lat, src_lon)
        metro_dst = self.nearest("MetroStation", dst_lat, dst_lon)

        def within(stop, radius):
            return stop is not None and stop["distance_m"] <= radius

        return {
            "bus_available": within(bus_src, self.BUS_RADIUS_M) and within(bus_dst, self.BUS_RADIUS_M),
            "metro_available": within(metro_src, self.METRO_RADIUS_M) and within(metro_dst, self.METRO_RADIUS_M),
            "bus_near_source": bus_src,
            "bus_near_destination": bus_dst,
            "metro_near_source": metro_src,
            "metro_near_destination": metro_dst,
            "rule": (f"bus stop within {self.BUS_RADIUS_M} m and metro station within "
                     f"{self.METRO_RADIUS_M} m of BOTH start and end"),
        }
