# graph_db/neo4j_connection.py

import logging

from neo4j import GraphDatabase
from config.settings import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    NEO4J_DATABASE,
    require_neo4j_settings,
)

# The driver prints a WARNING when a query mentions something that does not exist yet (for example
# HAS_WEATHER before any weather is stored). That is expected here and not an error, so keep the console clean.
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)


class Neo4jConnection:
    def __init__(self):
        require_neo4j_settings()
        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
            max_connection_lifetime=1000,
            max_connection_pool_size=50,
            connection_timeout=30
        )

    def execute(self, query, parameters=None):
        """
        Execute a write/read query and return fully materialized results.
        Compatible with Neo4j 5/6 and Aura.
        """
        with self.driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(query, parameters or {})
            return result.data()   # cleaner & faster

    def close(self):
        if self.driver:
            self.driver.close()