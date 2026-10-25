# 🚦 Urban Mobility Optimizer

### GraphRAG + LLM Powered Smart Transportation Analysis

![Python](https://img.shields.io/badge/Python-3.10-blue)
![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-red)
![Neo4j](https://img.shields.io/badge/GraphDB-Neo4j-green)
![LLM](https://img.shields.io/badge/LLM-GPT--OSS%2020B%20(Groq)-purple)
![Deployment](https://img.shields.io/badge/Deployment-Streamlit%20Cloud-orange)

---

# 🌍 Live Application

👉 **Try the app here**

```
https://urban-mobility-optimizer-using-llm-and-graphrag.streamlit.app/
```

---

# 📌 Project Overview

The **Urban Mobility Optimizer** is an AI-powered decision support system that helps commuters choose the most efficient transportation option within a city environment.

Unlike traditional navigation systems that only provide routes, this system:

* Compares **multiple transport modes**
* Evaluates **travel cost and time**
* Integrates **real-time weather data**
* Uses **GraphRAG + LLM reasoning**
* Generates **explainable travel recommendations**

The system is currently built for **Hyderabad's urban mobility network**.

---

# 🎯 Problem Statement

Most navigation systems provide routes but fail to answer key questions such as:

* Which transportation option is **most economical**?
* Which is **fastest during current conditions**?
* Which option provides the **best balance between cost and time**?

Urban commuters need **explainable decision support**, not just route suggestions.

This project solves that problem using:

* **Graph Databases**
* **Agent-based AI architecture**
* **LLM-powered reasoning**

---

# 🚀 Key Features

✅ True **distance-weighted shortest path (Dijkstra)** on the OpenStreetMap road network of Hyderabad
✅ Multi-mode transport comparison (**Car / Bus / Metro**)
✅ Travel cost estimation and time calculation
✅ Public transport availability detection
✅ Real-time weather integration using **Open-Meteo API**
✅ Graph context from **Neo4j AuraDB** (nearest bus stops / metro stations, stored weather) passed to the LLM
✅ **LLM tool-calling agent** that chooses which tools to run (with a fixed-pipeline fallback)
✅ AI-generated explanation using an LLM on **Groq** (default `openai/gpt-oss-20b`, set with `LLM_MODEL`)
✅ Interactive **Streamlit dashboard**
✅ Cost vs Travel Time visualization
✅ Map showing the computed route

---

# 🧠 System Architecture

The system has two planning modes, selectable in the sidebar:

* **Agent mode (default)** – an LLM on Groq (default `openai/gpt-oss-20b`) receives the trip and a set of tools, and **decides which tools to call, in what order, and when to stop**. It can skip steps (e.g. no public-transport check for a very short trip) and react to failures (e.g. retry routing with a larger snap distance). A step limit, argument validation and duplicate-call protection keep it safe. If the LLM cannot be used, the app **falls back to the fixed pipeline** and says why.
* **Fixed pipeline** – the same steps always run in the same order.

In both modes, cost/time estimation and the final explanation are deterministic finishing steps, not agent decisions. Every run shows a **tool-call trace** so you can see who decided what.

```
User Input (Streamlit UI)
        │
        ▼
Orchestrator ── mode: Agent ──► LLM tool-calling loop (agents/agent_loop.py)
        │                          │  chooses among:
        │                          ├── find_route         → Route Agent   (Dijkstra, routing/road_graph.py)
        │                          ├── get_weather        → Weather Agent (Open-Meteo)
        │                          ├── check_transport    → Transport Agent (Neo4j: nearest stops, both ends)
        │                          └── get_graph_context  → GraphRAG Agent  (Neo4j facts for the explanation)
        │
        └── mode: Fixed ──► same four tools in a fixed order (PlannerAgent.FIXED_PLAN)
                   │
                   ▼
        Cost Agent (deterministic estimates)  →  facts (cheapest / fastest / balanced computed in Python)
                   │
                   ▼
        LLM explanation (Groq GPT-OSS 20B, grounded in the facts; template fallback if unavailable)
                   │
                   ▼
        Explainable travel recommendation + route map + tool-call trace
```

> **Why routing is not done in Neo4j:** Cypher `shortestPath()` minimises the *number of road segments*, not distance, and was capped at 120 hops – it returned inflated distances (≈29 km for a ≈16.6 km trip) and "No route found" for longer trips. Routing now runs Dijkstra in memory on the same `nodes.csv` / `road_segments.csv` used to build the graph. Neo4j is still used for transport lookups and graph context.

---

# 🗂 Project Structure

```
urban-mobility-optimizer-using-llm-and-graphrag/
│
├── agents/
│   ├── orchestrator.py        # modes, fallback, deterministic finishing steps
│   ├── agent_loop.py          # LLM tool-calling loop + safety rails
│   ├── tools.py               # tool definitions + safe tool execution / trace
│   ├── planner_agent.py       # fixed plan used by the fixed pipeline
│   ├── route_agent.py
│   ├── weather_agent.py
│   ├── cost_agent.py
│   ├── transport_agent.py
│   └── graph_rag_agent.py
│
├── routing/
│   └── road_graph.py          # Dijkstra on the road network (scipy sparse)
│
├── config/settings.py         # reads secrets from environment variables only
├── data/                      # nodes, road_segments, bus_stops, metro_stations (cleaned)
├── data_ingestion/            # OSM road / bus / metro download + Open-Meteo weather
├── graph_db/                  # Neo4j connection, schema, loader
├── llm/
│   ├── llm_client.py
│   └── prompt_templates.py    # grounded prompt + deterministic facts + template fallback
├── scripts/
│   ├── clean_metro_stations.py
│   ├── reload_transport_nodes.py
│   └── manual_checks/         # live-DB scripts (need real credentials)
├── tests/                     # pytest suite (no network / DB needed)
├── ui/app.py
├── run_graph_load.py
├── .env.example
├── requirements.txt / requirements-dev.txt
└── README.md
```

---

# 🛠 Technologies Used

## Programming

* Python

## Graph Database

* **Neo4j AuraDB**

## AI / LLM

* **Groq API**
* **GPT-OSS 20B** (originally Llama 3.1 8B, which Groq retired on 16 Aug 2026)

## Data Processing

* Pandas
* NumPy / SciPy (Dijkstra routing)
* OSMnx
* NetworkX

## Visualization

* Matplotlib
* Streamlit

## APIs

* OpenStreetMap (Road Network Data)
* Open-Meteo API (Weather Data)

---

# ☁️ Deployment Architecture

```
User Browser
      │
      ▼
Streamlit Cloud (Frontend UI)
      │
      ▼
Python Backend
      │
      ├── Neo4j AuraDB
      │       → Nearest stops / graph context queries
      │
      ├── Open-Meteo API
      │       → Weather data
      │
      └── Groq LLM API
              → AI explanation generation
```

---

# ⚙️ Setup Instructions

## 1️⃣ Clone Repository

```bash
git clone https://github.com/manasiwaghmare18/urban-mobility-optimizer-using-llm-and-graphrag.git
cd urban-mobility-optimizer-using-llm-and-graphrag
```

---

## 2️⃣ Create Virtual Environment

```
python -m venv venv
```

Activate environment

Windows

```
venv\Scripts\activate
```

Linux / Mac

```
source venv/bin/activate
```

---

## 3️⃣ Install Dependencies

```
pip install -r requirements.txt
```

---

# 🔐 Environment Configuration

Copy `.env.example` to `.env` (git-ignored) and fill it in. On Streamlit Cloud, put the same names under **App settings → Secrets**. Credentials are never stored in the code.

```
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=neo4j

GROQ_API_KEY=gsk_xxxxxxxxxxxxx
```

---

# 🗄 Load Graph Data

```
python run_graph_load.py
```

This loads the road network, bus stops, metro stations and road segments into Neo4j using batched writes (minutes, not hours) and then checks the counts against the CSV files. It is safe to re-run.

```
python run_graph_load.py --dry-run   # show what would be loaded, no database needed
python run_graph_load.py --only roads # re-run a single stage (locations / roads / bus / metro)
```

If you are upgrading an existing database, replace the old metro nodes with the cleaned list (Hyderabad Metro only – the earlier file also contained suburban rail, under-construction and duplicate stations):

```
python scripts/reload_transport_nodes.py --yes
```

---

# ▶ Run Application

```
streamlit run ui/app.py
```

Open browser

```
http://localhost:8501
```

---

# 📊 Example Output

The system displays:

* Route distance
* Weather conditions
* Transport availability
* Cost comparison table
* Travel time comparison
* AI-generated explanation
* Cost vs Time visualization
* Map showing the computed route
* Tool-call trace (which tools ran, who decided, how long, what they returned)

---

# 🧪 Tests

```
pip install -r requirements-dev.txt
pytest
```

The suite needs no network, Neo4j or Groq key (they are faked). It covers routing correctness (including a regression test that distance-based routing beats hop-count routing), transport availability, the agent loop's failure handling, fallback behaviour and a headless run of the Streamlit app.

---

# ⚠️ Known Limitations

* Cost and time are **estimates** from fixed assumptions (₹/km and average speeds, one road distance for all modes). Live traffic, fares, walking and waiting time are not modelled.
* The road network covers a smaller area than the bus-stop download box; stops more than 1 km from any road are hidden in the UI.
* Stored weather in Neo4j covers only a sample of road segments; live weather is fetched per request.
* The small LLM can occasionally pick a poor tool order; the safety net always guarantees a route and cost, and the trace shows what happened.

---

# 🔮 Future Improvements

Potential enhancements include:

* Integration of **real-time traffic data**
* **Multi-city expansion**
* **Carbon emission analysis**
* **Personalized travel recommendations**
* **Voice-enabled travel assistant**

---

# 👨‍💻 Author

**Mansi Omprakash Waghmare**
PG-DBDA
C-DAC Hyderabad

# Default Page of App

<p align="center">
  <img src="Screenshots/Default page of App.png" alt="Streamlit App Default Page" width="900">
</p>


# ⭐ If You Like This Project

Consider giving the repository a **star ⭐**.

---


