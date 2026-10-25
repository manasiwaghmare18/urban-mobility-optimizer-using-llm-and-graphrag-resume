# agents/route_agent.py
from routing.road_graph import DEFAULT_MAX_SNAP_M, get_road_graph


class RouteAgent:
    """
    Finds the shortest DRIVABLE route by distance (Dijkstra on road-segment length).

    The Neo4j connection argument is kept so existing call sites (RouteAgent(conn)) still
    work, but routing no longer goes through Cypher shortestPath(), which minimised hop
    count instead of distance. See routing/road_graph.py for the details.
    """

    def __init__(self, conn=None, road_graph=None):
        self.conn = conn
        self._road_graph = road_graph
        self.last_error = None
        self.last_hint = None

    @property
    def road_graph(self):
        if self._road_graph is None:
            self._road_graph = get_road_graph()
        return self._road_graph

    def find_route(self, src_lat, src_lon, dst_lat, dst_lon, max_snap_m=DEFAULT_MAX_SNAP_M):
        """Return a route dict, or None (and set .last_error / .last_hint) on failure."""
        result = self.road_graph.route(
            float(src_lat), float(src_lon), float(dst_lat), float(dst_lon),
            max_snap_m=float(max_snap_m),
        )
        if not result["ok"]:
            self.last_error = result["error"]
            self.last_hint = result.get("hint")
            return None

        self.last_error = None
        self.last_hint = None
        return result
