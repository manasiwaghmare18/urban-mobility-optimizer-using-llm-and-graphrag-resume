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
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )

    def close(self):
        self.driver.close()

    def execute(self, query, parameters=None):
        """
        Always return fully materialized records.
        This avoids ResultConsumedError in Neo4j 5.x.
        """
        with self.driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]
