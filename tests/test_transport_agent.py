from agents.transport_agent import TransportAgent
from tests.conftest import FakeConn


def test_available_when_stops_near_both_ends():
    t = TransportAgent(FakeConn(bus_m=200, metro_m=500)).check_availability(17.4, 78.4, 17.5, 78.5)
    assert t["bus_available"] and t["metro_available"]


def test_not_available_when_only_one_end_is_served():
    # bus lookups are made for the source first, then the destination
    conn = FakeConn(bus_by_call=[200.0, 5000.0], metro_m=500)
    t = TransportAgent(conn).check_availability(17.4, 78.4, 17.5, 78.5)
    assert t["bus_available"] is False        # old code returned True ("near EITHER end")
    assert t["metro_available"] is True


def test_metro_radius_applies():
    t = TransportAgent(FakeConn(metro_m=2000)).check_availability(17.4, 78.4, 17.5, 78.5)
    assert t["metro_available"] is False


def test_label_is_whitelisted():
    import pytest
    with pytest.raises(ValueError):
        TransportAgent(FakeConn()).nearest("Location) DETACH DELETE (n", 1, 1)
