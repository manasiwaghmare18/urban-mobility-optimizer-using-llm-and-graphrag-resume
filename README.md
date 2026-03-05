# Urban-Mobility-Optimizer-Using-LLM-and-GraphRAG
Urban Mobility Optimizer using Neo4j and LLM orchestration. Provides intelligent route planning, travel time &amp; cost estimation, weather-aware road analysis, and bus/metro availability using real Hyderabad road network data. Built with Python, Graph DB, and agent-based reasoning.

https://urban-mobility-optimizer-using-llm-and-graphrag.streamlit.app/

# platform: 'Python, Streamlit, Neo4j',
# description: `Intelligent urban travel analysis system designed to help users choose the most suitable transportation mode within a city environment, specifically Hyderabad.

# The system combines:
- Graph-based city modeling (Neo4j)
- Large Language Models (LLMs)
- Graph Retrieval-Augmented Generation (GraphRAG)

# Features:
- Shortest-path route computation using city road graphs
- Real-time weather integration (Open-Meteo)
- Cost and travel-time estimation for Car, Bus, and Metro
- Transport availability detection using spatial graph queries
- Fully agentic AI pipeline (Planner → Agents → Orchestrator)
- GraphRAG-based explanations grounded in city graph context
- Interactive Streamlit dashboard with charts and maps

# Technologies Used:
- Python, Streamlit, Neo4j, Ollama (Gemma), OpenStreetMap/OSMnx, Open-Meteo API, Matplotlib`

## Urban Mobility Optimizer helps users in Hyderabad choose the best way to travel by comparing car, bus, and metro options using real city data.

## The system uses a graph database (Neo4j) to understand road connections, nearby transport stops, and city structure before calculating distance, cost, and travel time.

## AI pipeline runs multiple agents (route, weather, cost, transport) that work independently and are coordinated by an orchestrator to analyze the journey step by step.

## Using LLM and GraphRAG, the project generates clear explanations based on city graph context and shows results through an interactive Streamlit dashboard with maps and charts.
