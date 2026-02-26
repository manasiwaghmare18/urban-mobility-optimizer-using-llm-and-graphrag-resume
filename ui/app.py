# ------------------------------------------------
# FIX PYTHON PATH
# ------------------------------------------------
import sys
import os
import streamlit
import neo4j
import pandas
import matplotlib

import requests
import openai

from dotenv import load_dotenv
import os

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ------------------------------------------------
# IMPORTS
# ------------------------------------------------
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from graph_db.neo4j_connection import Neo4jConnection
from agents.orchestrator import OrchestratorAgent

# ------------------------------------------------
# PAGE CONFIG
# ------------------------------------------------
st.set_page_config(
    page_title="Agentic AI Urban Mobility Optimizer",
    layout="wide"
)

# ------------------------------------------------
# CUSTOM CSS (SIDEBAR MAP BACKGROUND)
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
    st.markdown(
        "<p class='sidebar-text'>Hyderabad Smart Travel</p>",
        unsafe_allow_html=True
    )
    st.divider()

    st.markdown("### 📍 Select Route")
    source_name = st.selectbox("Source Location", location_names)
    destination_name = st.selectbox("Destination Location", location_names)

    find_clicked = st.button("🔍 Find Best Route")
    map_clicked = st.button("🗺️ Show Map")

# ------------------------------------------------
# MAIN CONTENT
# ------------------------------------------------
st.title("📊 Route Analysis")

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
        # -------------------------------
        # METRICS
        # -------------------------------
        col1, col2, col3 = st.columns(3)
        col1.metric("Distance (km)", result["distance_km"])
        col2.metric("Temperature (°C)", result["weather"]["avg_temperature"])
        col3.metric("Wind Speed (km/h)", result["weather"]["avg_windspeed"])

        # -------------------------------
        # COST & TIME TABLE
        # -------------------------------
        st.subheader("💰 Cost & ⏱ Travel Time")

        cost_df = pd.DataFrame([
            {"Mode": "Car", "Cost (₹)": result["cost"]["car_cost_rs"], "Time (min)": result["cost"]["car_time_min"]},
            {"Mode": "Bus", "Cost (₹)": result["cost"]["bus_cost_rs"], "Time (min)": result["cost"]["bus_time_min"]},
            {"Mode": "Metro", "Cost (₹)": result["cost"]["metro_cost_rs"], "Time (min)": result["cost"]["metro_time_min"]},
        ]).replace("N/A", "❌ Not Available")

        st.table(cost_df)

        # -------------------------------
        # TRANSPORT AVAILABILITY
        # -------------------------------
        st.subheader("🚍 Transport Availability")
        st.write("**Bus Available:**", result["transport"]["bus_available"])
        st.write("**Metro Available:**", result["transport"]["metro_available"])

        # -------------------------------
        # AI EXPLANATION
        # -------------------------------
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

        # -------------------------------
        # 📊 COST vs TIME ANALYSIS (SAFE)
        # -------------------------------
        st.subheader("📊 Cost vs Travel Time Analysis")

        modes = []
        costs = []
        times = []

        # Car is always available
        modes.append("Car")
        costs.append(result["cost"]["car_cost_rs"])
        times.append(result["cost"]["car_time_min"])

        # Bus (only if available)
        if result["transport"]["bus_available"]:
            modes.append("Bus")
            costs.append(result["cost"]["bus_cost_rs"])
            times.append(result["cost"]["bus_time_min"])

        # Metro (only if available)
        if result["transport"]["metro_available"]:
            modes.append("Metro")
            costs.append(result["cost"]["metro_cost_rs"])
            times.append(result["cost"]["metro_time_min"])

        chart_df = pd.DataFrame({
            "Mode": modes,
            "Cost": costs,
            "Time": times
        })

        fig, ax1 = plt.subplots(figsize=(8, 5))

        ax1.bar(chart_df["Mode"], chart_df["Cost"], alpha=0.7, label="Cost (₹)")
        ax1.set_ylabel("Cost (₹)")
        ax1.set_xlabel("Transport Mode")
        ax1.set_title("Cost vs Travel Time Comparison")
        ax1.grid(True, linestyle="--", alpha=0.4)

        ax2 = ax1.twinx()
        ax2.plot(
            chart_df["Mode"],
            chart_df["Time"],
            marker="o",
            color="orange",
            markerfacecolor="black",
            markeredgecolor="black",
            linewidth=2,
            label="Travel Time (min)"
        )
        ax2.set_ylabel("Travel Time (minutes)")

        ax1.legend(loc="upper left")
        ax2.legend(loc="upper right")

        st.pyplot(fig)

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
