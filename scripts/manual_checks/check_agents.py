"""Manual check - needs real credentials / network. Run from the project root: python scripts/manual_checks/check_agents.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from graph_db.neo4j_connection import Neo4jConnection
from agents.orchestrator import OrchestratorAgent

def main():
    print("=== END-TO-END RUN AGAINST LIVE NEO4J / GROQ ===")

    source = (17.4375, 78.4483)   # Ameerpet
    destination = (17.4401, 78.3489)  # Gachibowli

    conn = Neo4jConnection()
    orchestrator = OrchestratorAgent(conn)

    use_agent = "--fixed" not in sys.argv   # python scripts/manual_checks/check_agents.py --fixed
    result = orchestrator.handle_request(source, destination, labels=("Ameerpet", "Gachibowli"), use_agent=use_agent)
    conn.close()

    for k, v in result.items():
        if k not in ("trace", "route_path"):
            print(f"{k}: {v}")
    print("\ntrace:")
    for t in result.get("trace", []):
        print(f"  {t['step']:>2} {t['actor']:<8} {t['tool']:<18} {t['status']:<8} {t['ms']:>5} ms  {t['summary']}")

    print("\n✅ Run completed")

if __name__ == "__main__":
    main()
