# graph_db/neo4j_connection.py

from neo4j import GraphDatabase
from config.settings import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    NEO4J_DATABASE
)


class Neo4jConnection:
    def __init__(self):
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