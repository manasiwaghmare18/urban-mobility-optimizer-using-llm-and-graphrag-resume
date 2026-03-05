# 🚦 Urban Mobility Optimizer

### GraphRAG + LLM Powered Smart Transportation Analysis

![Python](https://img.shields.io/badge/Python-3.10-blue)
![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-red)
![Neo4j](https://img.shields.io/badge/GraphDB-Neo4j-green)
![LLM](https://img.shields.io/badge/LLM-Llama%203.1-purple)
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

✅ Graph-based shortest path computation using **Neo4j AuraDB**
✅ Multi-mode transport comparison (**Car / Bus / Metro**)
✅ Travel cost estimation and time calculation
✅ Public transport availability detection
✅ Real-time weather integration using **Open-Meteo API**
✅ GraphRAG contextual reasoning
✅ AI-generated explanation using **Llama 3.1 via Groq**
✅ Interactive **Streamlit dashboard**
✅ Cost vs Travel Time visualization
✅ Map-based route display

---

# 🧠 System Architecture

The system follows a **Fully Agentic AI Architecture**, where specialized agents collaborate to produce the final travel recommendation.

```
User Input (Streamlit UI)
        │
        ▼
Orchestrator Agent
        │
        ├── Route Agent
        │       → Computes shortest path using Neo4j graph
        │
        ├── Weather Agent
        │       → Fetches real-time weather
        │
        ├── Cost Agent
        │       → Calculates travel cost and time
        │
        ├── Transport Agent
        │       → Detects bus and metro availability
        │
        ├── GraphRAG Context Builder
        │       → Retrieves graph context from Neo4j
        │
        ▼
LLM Reasoning (Groq Llama 3.1)
        │
        ▼
Explainable Travel Recommendation
```

---

# 🗂 Project Structure

```
urban-mobility-optimizer/
│
├── agents/
│   ├── planner_agent.py
│   ├── route_agent.py
│   ├── weather_agent.py
│   ├── cost_agent.py
│   ├── transport_agent.py
│   ├── graph_rag_agent.py
│   └── orchestrator.py
│
├── config/
│   └── settings.py
│
├── data/
│   ├── bus_stops.csv
│   ├── metro_stations.csv
│   ├── nodes.csv
│   └── road_segments.csv
│
├── graph_db/
│   ├── neo4j_connection.py
│   ├── graph_schema.py
│   └── load_data.py
│
├── llm/
│   └── llm_client.py
│
├── ui/
│   └── app.py
│
├── weather/
│   └── weather_scraper.py
│
├── run_graph_load.py
├── requirements.txt
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
* **Llama 3.1 Model**

## Data Processing

* Pandas
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
      │       → Graph shortest path queries
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
git clone https://github.com/your-username/urban-mobility-optimizer.git
cd urban-mobility-optimizer
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

Create `.env` file

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

This loads:

* Road network
* Bus stops
* Metro stations
* Road segments

into Neo4j.

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
* Map showing selected route

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

---

# ⭐ If You Like This Project

Consider giving the repository a **star ⭐**.

---


