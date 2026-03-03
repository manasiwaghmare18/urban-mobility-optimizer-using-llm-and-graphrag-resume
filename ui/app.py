# ------------------------------------------------
# FIX PYTHON PATH (MUST BE FIRST)
# ------------------------------------------------
import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ------------------------------------------------
# IMPORTS
# ------------------------------------------------
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from dotenv import load_dotenv
load_dotenv()

from graph_db.neo4j_connection import Neo4jConnection
from graph_db.load_data import GraphLoader
from agents.orchestrator import OrchestratorAgent
from weather_scraper import enrich_roads_with_weather

# ------------------------------------------------
# PAGE CONFIG
# ------------------------------------------------
st.set_page_config(
    page_title="Agentic AI Urban Mobility Optimizer",
    layout="wide"
)

# ------------------------------------------------
# CUSTOM SIDEBAR STYLE
# ------------------------------------------------
st.markdown("""
<style>
[data-testid="stSidebar"] {
    background-image: url("https://upload.wikimedia.org/wikipedia/commons/e/ec/OpenStreetMap_Hyderabad.png");
    background-size: cover;
    background-position: center;
}
[data-testid="stSidebar"] > div {
    background: rgba(0,0,0,0.65);
}
.sidebar-text {
    color: white;
}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------
# SESSION STATE
# ------------------------------------------------
if "result" not in st.session_state:
    st.session_state.result = None

# ------------------------------------------------
# LOAD LOCATIONS
# ------------------------------------------------
@st.cache_data
def load_locations():
    df = pd.read_csv(os.path.join(PROJECT_ROOT, "data", "bus_stops.csv"))
    return df.dropna(subset=["lat", "lon", "name"])

locations_df = load_locations()
location_names = locations_df["name"].tolist()

# ------------------------------------------------
# SIDEBAR
# ------------------------------------------------
with st.sidebar:
    st.markdown("## 🚦 Urban Mobility AI")
    st.markdown("<p class='sidebar-text'>Hyderabad Smart Travel</p>", unsafe_allow_html=True)
    st.divider()

    st.markdown("### 📍 Select Route")
    source_name = st.selectbox("Source Location", location_names)
    destination_name = st.selectbox("Destination Location", location_names)

    find_clicked = st.button("🔍 Find Best Route")
    map_clicked = st.button("🗺️ Show Map")

    st.divider()
    update_weather_clicked = st.button("🌦 Update Live Weather")

# ------------------------------------------------
# MAIN TITLE
# ------------------------------------------------
st.title("📊 Route Analysis")

# ------------------------------------------------
# LIVE WEATHER UPDATE
# ------------------------------------------------
# ------------------------------------------------
# LIVE WEATHER UPDATE (FIXED VERSION)
# ------------------------------------------------
if update_weather_clicked:

    with st.spinner("Fetching live weather and updating graph..."):

        conn = Neo4jConnection()
        loader = GraphLoader()

        # 1️⃣ Fetch road connections
        road_segments = conn.execute("""
            MATCH (a:Location)-[:CONNECTS]->(b:Location)
            RETURN a.id AS from_node,
                   b.id AS to_node
            LIMIT 100
        """)

        # 2️⃣ Fetch node coordinates
        nodes = conn.execute("""
            MATCH (l:Location)
            RETURN l.id AS id,
                   l.lat AS latitude,
                   l.lon AS longitude
        """)

        # IMPORTANT: DO NOT convert to int
        node_dict = {
            str(n["id"]): {
                "latitude": float(n["latitude"]),
                "longitude": float(n["longitude"])
            }
            for n in nodes
        }

        road_list = [
            {
                "from_node": str(r["from_node"]),
                "to_node": str(r["to_node"])
            }
            for r in road_segments
        ]

        st.write("Road segments fetched:", len(road_list))

        enriched = enrich_roads_with_weather(road_list, node_dict)

        st.write("Enriched segments:", len(enriched))

        if enriched:
            st.write("Sample weather object:", enriched[0].get("weather"))

        loader.load_weather(enriched)

        conn.close()
        loader.close()

        st.success("✅ Live weather updated successfully!")

# ------------------------------------------------
# RUN AGENTIC PIPELINE
# ------------------------------------------------
if find_clicked:
    with st.spinner("Analyzing route using fully agentic AI pipeline..."):

        src = locations_df[locations_df["name"] == source_name].iloc[0]
        dst = locations_df[locations_df["name"] == destination_name].iloc[0]

        source = (float(src["lat"]), float(src["lon"]))
        destination = (float(dst["lat"]), float(dst["lon"]))

        conn = Neo4jConnection()
        orchestrator = OrchestratorAgent(conn)

        st.session_state.result = orchestrator.handle_request(
            source, destination
        )

        conn.close()

# ------------------------------------------------
# DISPLAY RESULTS
# ------------------------------------------------
if st.session_state.result:
    result = st.session_state.result

    if "error" in result:
        st.error(result["error"])
    else:

        col1, col2, col3 = st.columns(3)
        col1.metric("Distance (km)", result["distance_km"])
        col2.metric("Temperature (°C)", result["weather"]["avg_temperature"])
        col3.metric("Wind Speed (km/h)", result["weather"]["avg_windspeed"])

        st.subheader("💰 Cost & ⏱ Travel Time")

        cost_df = pd.DataFrame([
            {"Mode": "Car", "Cost (₹)": result["cost"]["car_cost_rs"], "Time (min)": result["cost"]["car_time_min"]},
            {"Mode": "Bus", "Cost (₹)": result["cost"]["bus_cost_rs"], "Time (min)": result["cost"]["bus_time_min"]},
            {"Mode": "Metro", "Cost (₹)": result["cost"]["metro_cost_rs"], "Time (min)": result["cost"]["metro_time_min"]},
        ]).replace("N/A", "❌ Not Available")

        st.table(cost_df)

        st.subheader("🚍 Transport Availability")
        st.write("**Bus Available:**", result["transport"]["bus_available"])
        st.write("**Metro Available:**", result["transport"]["metro_available"])

        st.subheader("🤖 AI Explanation")
        st.markdown(
            f"""
            <div style="
                background-color:#0f2a44;
                padding:22px;
                border-radius:14px;
                color:white;
                white-space: pre-line;
                font-size:16px;
                line-height:1.7;
            ">
            {result['llm_explanation']}
            </div>
            """,
            unsafe_allow_html=True
        )

# ------------------------------------------------
# MAP VIEW
# ------------------------------------------------
if map_clicked:
    st.subheader("🗺️ Selected Route Map")

    map_df = pd.DataFrame([
        {
            "lat": locations_df[locations_df["name"] == source_name]["lat"].iloc[0],
            "lon": locations_df[locations_df["name"] == source_name]["lon"].iloc[0]
        },
        {
            "lat": locations_df[locations_df["name"] == destination_name]["lat"].iloc[0],
            "lon": locations_df[locations_df["name"] == destination_name]["lon"].iloc[0]
        }
    ])

    st.map(map_df)