# graph_db/graph_schema.py

def create_constraints(conn):
    queries = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (l:Location) REQUIRE l.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (r:RoadSegment) REQUIRE r.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (b:BusStop) REQUIRE b.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (m:MetroStation) REQUIRE m.id IS UNIQUE"
        "CREATE CONSTRAINT IF NOT EXISTS FOR (w:Weather) REQUIRE w.location_id IS UNIQUE"
    ]

    for q in queries:
        conn.execute(q)

    print("Graph constraints created.")
