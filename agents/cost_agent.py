# agents/cost_agent.py
class CostAgent:
    """
    Rough cost / time estimate per mode from the road distance.

    These are ASSUMPTIONS, not live fares or traffic data. They are exposed in
    ASSUMPTIONS so the explanation can state them honestly.
    """

    SHORT_TRIP_KM = 1.5   # below this the app treats the trip as "very short" (walking is a real option)
    WALK_SPEED = 5        # km/h
    CAR_SPEED = 25     # km/h, urban average
    BUS_SPEED = 18
    METRO_SPEED = 35
    CAR_RS_PER_KM = 12
    BUS_RS_PER_KM = 2
    METRO_RS_PER_KM = 3

    ASSUMPTIONS = (
        f"Car Rs {CAR_RS_PER_KM}/km at {CAR_SPEED} km/h; bus Rs {BUS_RS_PER_KM}/km at {BUS_SPEED} km/h; "
        f"metro Rs {METRO_RS_PER_KM}/km at {METRO_SPEED} km/h. All modes use the same road distance; "
        "walking, waiting and live traffic are not modelled."
    )

    def walk_minutes(self, distance_m) -> int:
        return round(distance_m / 1000 / self.WALK_SPEED * 60)

    def estimate(self, distance_m, bus_available=True, metro_available=True):
        """
        distance_m: road distance in metres.
        Modes that are not available get None for both cost and time (never the string "N/A").
        """
        km = distance_m / 1000

        def mode(rate, speed, available=True):
            if not available:
                return None, None
            return round(km * rate, 2), round((km / speed) * 60, 1)

        car_cost, car_time = mode(self.CAR_RS_PER_KM, self.CAR_SPEED)
        bus_cost, bus_time = mode(self.BUS_RS_PER_KM, self.BUS_SPEED, bus_available)
        metro_cost, metro_time = mode(self.METRO_RS_PER_KM, self.METRO_SPEED, metro_available)

        return {
            "car_cost_rs": car_cost, "car_time_min": car_time,
            "bus_cost_rs": bus_cost, "bus_time_min": bus_time,
            "metro_cost_rs": metro_cost, "metro_time_min": metro_time,
        }
