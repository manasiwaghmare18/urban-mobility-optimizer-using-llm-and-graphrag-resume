# ------------------------------------------------
# FIX PYTHON PATH (MUST BE FIRST)
# ------------------------------------------------
import os
import re
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ------------------------------------------------
# IMPORTS
# ------------------------------------------------
import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agents.cost_agent import CostAgent
from agents.orchestrator import OrchestratorAgent
from agents.transport_agent import TransportAgent
from data_ingestion.weather_sample import fetch_weather_parallel, pick_spread_segments
from graph_db.load_data import GraphLoader
from graph_db.neo4j_connection import Neo4jConnection
from llm import llm_client
from llm.prompt_templates import recommendation_reason
from routing.road_graph import DEFAULT_MAX_SNAP_M, get_road_graph
from ui import theme

st.set_page_config(page_title="Urban Mobility Optimizer", page_icon="🚦", layout="wide",
                   initial_sidebar_state="auto")   # open on desktop, collapsed on phones
st.markdown(theme.CSS, unsafe_allow_html=True)

AGENT, FIXED = "Agent", "Fixed"
SHORT_TRIP_KM = CostAgent.SHORT_TRIP_KM
MODE_NOTES = {AGENT: "An LLM decides which tools to run, in what order, and when to stop.",
              FIXED: "The same steps run in the same order every time."}


def stretch(fn, *args, **kwargs):
    """Full-width widget that works on newer Streamlit (width="stretch") and older (use_container_width)."""
    try:
        return fn(*args, width="stretch", **kwargs)
    except TypeError:
        return fn(*args, use_container_width=True, **kwargs)


# ------------------------------------------------
# DATA LOADING
# ------------------------------------------------
@st.cache_resource(show_spinner="Loading road network...")
def load_road_graph():
    return get_road_graph()


SMALL_WORDS = {"of", "and", "the", "to", "at", "in", "near", "on"}


def clean_name(name) -> str:
    """Tidy stop names: 'gachibowli flyover bustop' -> 'Gachibowli Flyover Bus Stop'."""
    text = re.sub(r"\s+", " ", str(name)).strip()
    text = re.sub(r"(?i)\bbus ?s?top\b", "Bus Stop", text)   # also fixes the "bustop" typo in the data
    words = []
    for i, w in enumerate(text.split(" ")):
        keep = w.isupper() or any(c.isupper() for c in w[1:]) or (w.lower() in SMALL_WORDS and i > 0)
        words.append(w if keep else w[:1].upper() + w[1:])
    return " ".join(words)


@st.cache_data(show_spinner=False)
def load_locations():
    """
    Bus stops + metro stations that can actually be routed (unnamed / outside the road network hidden).
    Duplicate names get their coordinates appended so every option is unique.
    """
    graph = load_road_graph()
    frames = []
    for filename, kind, icon in (("bus_stops.csv", "Bus stop", "🚌"),
                                 ("metro_stations.csv", "Metro station", "🚇")):
        df = pd.read_csv(os.path.join(PROJECT_ROOT, "data", filename)).dropna(subset=["lat", "lon", "name"])
        df["kind"], df["icon"] = kind, icon
        df["name_clean"] = df["name"].map(clean_name)
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)

    df["snap_m"] = [graph.snap(r.lat, r.lon)[1] for r in df.itertuples()]
    total = len(df)
    df = df[df["snap_m"] <= DEFAULT_MAX_SNAP_M].copy()

    df["label"] = df["icon"] + " " + df["name_clean"]
    dup = df["label"].duplicated(keep=False)
    df.loc[dup, "label"] = (df.loc[dup, "label"] + " · " + df.loc[dup, "lat"].round(4).astype(str)
                            + ", " + df.loc[dup, "lon"].round(4).astype(str))
    df = df.drop_duplicates("label")
    df = df.sort_values("name_clean", key=lambda s: s.str.lower()).reset_index(drop=True)
    return df, total - len(df)


locations_df, hidden_count = load_locations()
location_labels = locations_df["label"].tolist()


def find_label(name: str, kind: str):
    hit = locations_df[(locations_df["name_clean"].str.lower() == name.lower()) & (locations_df["kind"] == kind)]
    return hit.iloc[0]["label"] if len(hit) else None


EXAMPLES = [
    ("Ameerpet Metro → Gachibowli", find_label("Ameerpet (Red Line)", "Metro station"),
     find_label("Gachibowli Flyover Bus Stop", "Bus stop")),
    ("Chhota Anjaiah Nagar → Public Library", find_label("Chhota Anjaiah Nagar", "Bus stop"),
     find_label("Public Library", "Bus stop")),
    ("Short hop: Ameerpet Metro → Ameerpet", find_label("Ameerpet (Red Line)", "Metro station"),
     find_label("Ameerpet", "Bus stop")),
]
EXAMPLES = [e for e in EXAMPLES if e[1] and e[2]]

# session defaults (set before the widgets are created)
default_from = EXAMPLES[0][1] if EXAMPLES else location_labels[0]
default_to = EXAMPLES[0][2] if EXAMPLES else location_labels[min(1, len(location_labels) - 1)]
st.session_state.setdefault("source", default_from)
st.session_state.setdefault("destination", default_to)
st.session_state.setdefault("result", None)


def swap_locations():
    st.session_state.source, st.session_state.destination = (
        st.session_state.destination, st.session_state.source)


def use_example(source, destination):
    st.session_state.source, st.session_state.destination = source, destination
    st.session_state.run_now = True


def row_for(label):
    return locations_df[locations_df["label"] == label].iloc[0]


def plain(label: str) -> str:
    """Stop name without the emoji prefix, for headings and map labels."""
    return row_for(label)["name_clean"]


# ------------------------------------------------
# SIDEBAR
# ------------------------------------------------
update_weather_clicked = False
with st.sidebar:
    st.markdown(theme.brand(), unsafe_allow_html=True)

    st.markdown('<div class="umo-side-label">Route</div>', unsafe_allow_html=True)
    st.selectbox("From", location_labels, key="source")
    st.selectbox("To", location_labels, key="destination")
    st.button("⇅  Swap", on_click=swap_locations, help="Swap start and destination")
    if hidden_count:
        st.markdown(f'<div class="umo-side-note">{hidden_count} stops are hidden because they lie '
                    "outside the road network.</div>", unsafe_allow_html=True)

    st.markdown('<div class="umo-side-label">Planning mode</div>', unsafe_allow_html=True)
    run_mode = st.radio("Planning mode", [AGENT, FIXED], horizontal=True, key="mode",
                        label_visibility="collapsed")
    st.markdown(f'<div class="umo-side-note">{theme.esc(MODE_NOTES[run_mode])}</div>', unsafe_allow_html=True)

    st.write("")
    find_clicked = stretch(st.button, "🔍 Find Best Route", type="primary")

    st.divider()
    with st.expander("🛠 Data tools"):
        st.markdown('<div class="umo-side-note">Stores current weather on about 40 locations across the city '
                    "in the Neo4j graph. Optional: live weather is always fetched per request.</div>",
                    unsafe_allow_html=True)
        update_weather_clicked = stretch(st.button, "🌦 Update Live Weather")

# ------------------------------------------------
# LIVE WEATHER UPDATE
# Order matters: fetch from the web FIRST (no database connection open), then connect to Neo4j
# just for the write. Aura closes idle connections, which broke the old "connect first" order.
# ------------------------------------------------
@st.cache_data(show_spinner=False)
def weather_sample():
    nodes_df = pd.read_csv(os.path.join(PROJECT_ROOT, "data", "nodes.csv"))
    roads_df = pd.read_csv(os.path.join(PROJECT_ROOT, "data", "road_segments.csv"),
                           usecols=["from_node", "to_node"])
    segments = pick_spread_segments(nodes_df, roads_df)
    wanted = {n for s in segments for n in (s["from_node"], s["to_node"])}
    lookup = {int(r.node_id): {"latitude": float(r.latitude), "longitude": float(r.longitude)}
              for r in nodes_df[nodes_df["node_id"].isin(wanted)].itertuples()}
    return segments, lookup


if update_weather_clicked:
    with st.spinner("Fetching live weather for locations across the city..."):
        loader = None
        try:
            segments, lookup = weather_sample()
            enriched = fetch_weather_parallel(segments, lookup)          # web calls only
            with_weather = [s for s in enriched if s.get("weather")]
            if not with_weather:
                st.error("The weather service returned no data. Please try again in a minute.")
            else:
                loader = GraphLoader()                                    # connect only now
                loader.load_weather(with_weather)
                st.success(f"✅ Live weather stored on {len(with_weather)} of {len(segments)} "
                           "locations spread across the city.")
        except Exception as exc:
            st.error(f"Weather update failed: {exc}")
        finally:
            if loader is not None:
                loader.close()

# ------------------------------------------------
# RUN THE ANALYSIS
# ------------------------------------------------
run_requested = find_clicked or st.session_state.pop("run_now", False)
if run_requested:
    if st.session_state.source == st.session_state.destination:
        st.warning("Please choose two different locations.")
    else:
        with st.spinner("Analyzing route..."):
            src, dst = row_for(st.session_state.source), row_for(st.session_state.destination)
            conn = None
            try:
                conn = Neo4jConnection()
                orchestrator = OrchestratorAgent(conn, road_graph=load_road_graph())
                st.session_state.result = orchestrator.handle_request(
                    (float(src["lat"]), float(src["lon"])),
                    (float(dst["lat"]), float(dst["lon"])),
                    labels=(src["name_clean"], dst["name_clean"]),
                    use_agent=(run_mode == AGENT),
                )
            except Exception as exc:
                st.session_state.result = {"error": f"Could not run the analysis: {exc}", "trace": []}
            finally:
                if conn is not None:
                    conn.close()


# ------------------------------------------------
# DISPLAY HELPERS
# ------------------------------------------------
def why_unavailable(mode: str, transport) -> str:
    if transport is None:
        return ""
    radius = TransportAgent.BUS_RADIUS_M if mode == "Bus" else TransportAgent.METRO_RADIUS_M
    noun = "bus stop" if mode == "Bus" else "metro station"
    parts = []
    for role, key in (("start", f"{mode.lower()}_near_source"), ("destination", f"{mode.lower()}_near_destination")):
        stop = transport.get(key)
        if stop is None:
            parts.append(f"No {noun} was found near the {role}.")
        elif stop["distance_m"] > radius:
            parts.append(f"Nearest {noun} to the {role} is {stop['distance_m'] / 1000:.1f} km away "
                         f"({stop['name'] or 'unnamed'}); the limit is {radius / 1000:.1f} km.")
    return " ".join(parts) or f"No {noun} within range of both ends."


def mode_tag(result) -> str:
    mode = result.get("mode", "")
    if mode == "agent":
        return theme.badge("Agent mode", "blue")
    if "fallback" in mode:
        return theme.badge("Fixed pipeline (agent fallback)", "amber")
    return theme.badge("Fixed pipeline", "grey")


def mode_charts(options: dict):
    df = pd.DataFrame([{"Mode": m, "Cost": o["cost"], "Time": o["time"],
                        "CostLabel": f"₹{o['cost']:,.0f}", "TimeLabel": f"{o['time']:.0f} min"}
                       for m, o in options.items()])
    order = list(df["Mode"])
    color = alt.Color("Mode:N", legend=None,
                      scale=alt.Scale(domain=list(theme.MODE_COLORS), range=list(theme.MODE_COLORS.values())))

    def one(field, label_field, title):
        top = float(df[field].max()) * 1.25
        y = alt.Y(f"{field}:Q", title=None, scale=alt.Scale(domain=[0, top]), axis=alt.Axis(tickCount=4, labelColor="#64748B"))
        x = alt.X("Mode:N", sort=order, title=None, axis=alt.Axis(labelAngle=0, labelFontSize=12, ticks=False, domain=False))
        bars = alt.Chart(df).mark_bar(cornerRadiusTopLeft=7, cornerRadiusTopRight=7, size=46).encode(
            x=x, y=y, color=color, tooltip=["Mode", alt.Tooltip(field, title=title, format=",.2f")])
        text = alt.Chart(df).mark_text(dy=-9, fontSize=12, fontWeight="bold", color="#0F172A").encode(
            x=x, y=y, text=f"{label_field}:N")
        return (bars + text).properties(height=230, title=alt.TitleParams(title, anchor="start", fontSize=13,
                                                                           fontWeight=700, color="#0F172A"))

    def finish(chart):
        return chart.configure(background="transparent").configure_view(strokeWidth=0).configure_axis(
            gridColor="#E2E8F0", domainColor="#CBD5E1")

    return (finish(one("Cost", "CostLabel", "Cost (₹)")),
            finish(one("Time", "TimeLabel", "Travel time (min)")))


def short(text: str, n: int = 32) -> str:
    """Truncate for map labels. ASCII "..." on purpose: deck.gl's text atlas drops characters like "…"."""
    return text if len(text) <= n else text[: n - 3] + "..."


def render_map(result):
    (slat, slon), (dlat, dlon) = result["source"], result["destination"]
    path = [[lon, lat] for lat, lon in result["route_path"]]
    points = [{"pos": [slon, slat], "name": result["source_label"], "color": [22, 163, 74],
               "label": short(result["source_label"], 30)},
              {"pos": [dlon, dlat], "name": result["destination_label"], "color": [220, 38, 38],
               "label": short(result["destination_label"], 30)}]

    view = pdk.data_utils.compute_view(path + [[slon, slat], [dlon, dlat]], 0.55)   # margin so labels stay inside
    view.zoom = max(9, min(15.5, view.zoom))

    layers = [
        pdk.Layer("PathLayer", data=[{"path": path}], get_path="path", get_color=[255, 255, 255],
                  get_width=11, width_min_pixels=7, cap_rounded=True, joint_rounded=True),
        pdk.Layer("PathLayer", data=[{"path": path}], get_path="path", get_color=[37, 99, 235],
                  get_width=6, width_min_pixels=4, cap_rounded=True, joint_rounded=True),
        pdk.Layer("ScatterplotLayer", data=points, get_position="pos", get_fill_color="color",
                  get_line_color=[255, 255, 255], stroked=True, line_width_min_pixels=3,
                  radius_units="pixels", get_radius=9, pickable=True),
        # NOTE: do not set font_family / font_weight / character_set here. In deck.gl they collapse the
        # label text to a few pixels (or crash the layer) - verified by rendering each variant.
        pdk.Layer("TextLayer", data=points, get_position="pos", get_text="label", get_size=13,
                  size_units="pixels", size_min_pixels=12, size_max_pixels=14,
                  get_color=[15, 23, 42], get_pixel_offset=[0, -30], background=True,
                  get_background_color=[255, 255, 255, 240], background_padding=[9, 5],
                  get_border_color=[203, 213, 225], get_border_width=1,
                  get_text_anchor="'middle'", get_alignment_baseline="'bottom'"),
    ]
    deck = pdk.Deck(layers=layers, initial_view_state=view, map_provider="carto", map_style="light",
                    tooltip={"html": "<b>{name}</b>", "style": {"backgroundColor": "#0F172A", "color": "white",
                                                                  "fontSize": "13px", "borderRadius": "8px"}})
    stretch(st.pydeck_chart, deck, height=440)
    st.markdown(theme.legend(result["source_label"], result["destination_label"], result["distance_km"]),
                unsafe_allow_html=True)


def render_result(result):
    facts, transport = result["facts"], result["transport"]
    options, status = facts["options"], facts["status"]
    weather = result.get("weather") or {}
    best = facts["balanced"]

    st.markdown(theme.route_header(result["source_label"], result["destination_label"], mode_tag(result)),
                unsafe_allow_html=True)

    temp, wind = weather.get("avg_temperature"), weather.get("avg_windspeed")
    total_ms = sum(t["ms"] for t in result["trace"])
    calls = sum(1 for t in result["trace"] if t["tool"] != "write_explanation")
    st.markdown(theme.kpi_row([
        theme.kpi("Road distance", f"{result['distance_km']:.2f}", "km",
                  f"straight line {result['straight_line_km']:.2f} km"),
        theme.kpi("Temperature", "—" if temp is None else f"{temp:.1f}", "" if temp is None else "°C",
                  "live, at route midpoint" if temp is not None else "not checked"),
        theme.kpi("Wind speed", "—" if wind is None else f"{wind:.1f}", "" if wind is None else "km/h",
                  "live, at route midpoint" if wind is not None else "not checked"),
        theme.kpi("Planning", "Agent" if result["mode"] == "agent" else "Fixed", "",
                  f"{calls} tool call{'s' if calls != 1 else ''} · {total_ms / 1000:.1f}s"),
    ]), unsafe_allow_html=True)

    short_trip = result["distance_km"] < SHORT_TRIP_KM and facts.get("walk_min") is not None
    if short_trip:
        st.markdown(theme.recommendation_walk(facts["walk_min"], result["distance_km"]), unsafe_allow_html=True)
        best = None                      # no motorised option gets the "recommended" ribbon
    elif best:
        st.markdown(theme.recommendation(best, options[best]["cost"], options[best]["time"],
                                         recommendation_reason(facts)),
                    unsafe_allow_html=True)

    st.markdown(theme.section("Options compared"), unsafe_allow_html=True)
    cards = []
    for name in ("Car", "Bus", "Metro"):
        label = status.get(name, "")
        cards.append(theme.mode_card(
            name, options.get(name), "Not checked" if label == "availability not checked" else "ok",
            best=(name == best), cheapest=(name == facts["cheapest"] and len(options) > 1),
            fastest=(name == facts["fastest"] and len(options) > 1),
            why_not=why_unavailable(name, transport)))
    st.markdown(theme.mode_row(cards), unsafe_allow_html=True)

    st.markdown(theme.section("Explanation and comparison"), unsafe_allow_html=True)
    left, right = st.columns([1.15, 1], gap="medium")
    with left:
        with st.container(key="card_explain"):
            src_badge = theme.badge("Written by LLM", "blue") if result["explanation_source"] == "llm" \
                else theme.badge("Built-in summary · LLM unavailable", "amber")
            st.markdown(theme.card_title("AI explanation", src_badge), unsafe_allow_html=True)
            st.markdown(result["llm_explanation"])
    with right:
        with st.container(key="card_chart"):
            st.markdown(theme.card_title("Cost and time"), unsafe_allow_html=True)
            cost_chart, time_chart = mode_charts(options)
            c1, c2 = st.columns(2)
            with c1:
                stretch(st.altair_chart, cost_chart)
            with c2:
                stretch(st.altair_chart, time_chart)

    st.markdown(theme.section("Route"), unsafe_allow_html=True)
    with st.container(key="card_map"):
        render_map(result)

    st.markdown(theme.section("How this answer was produced"), unsafe_allow_html=True)
    with st.expander("Tool-call trace", expanded=False):
        if result.get("fallback_reason"):
            st.warning(f"LLM planning was not (fully) used: {result['fallback_reason']}")
        st.markdown(theme.trace_table(result["trace"]), unsafe_allow_html=True)
        st.caption("“LLM agent” rows were chosen by the model. “Fixed code” rows are mandatory steps, "
                   "the cost calculation, the explanation, or a fallback.")


# ------------------------------------------------
# MAIN PAGE
# ------------------------------------------------
st.markdown(theme.banner(
    "Urban Mobility Optimizer",
    "Compare car, bus and metro for any trip across Hyderabad",
    ["Dijkstra road routing", "Neo4j city graph", "Live weather", "LLM tool-calling agent"]),
    unsafe_allow_html=True)

result = st.session_state.result
if not result:
    st.markdown(theme.section("Try an example"), unsafe_allow_html=True)
    cols = st.columns(len(EXAMPLES) or 1)
    for col, (title, a, b) in zip(cols, EXAMPLES):
        with col:
            stretch(st.button, title, key=f"ex_{title}", on_click=use_example, args=(a, b))
    st.markdown(theme.section("How it works"), unsafe_allow_html=True)
    st.markdown(theme.empty_state_steps(), unsafe_allow_html=True)
    st.write("")
    st.caption("Or choose a start and destination in the sidebar and click **Find Best Route**.")
elif "error" in result:
    st.error(result["error"])
    if result.get("trace"):
        with st.expander("Tool-call trace", expanded=True):
            st.markdown(theme.trace_table(result["trace"]), unsafe_allow_html=True)
else:
    render_result(result)

st.markdown(theme.footer(CostAgent.ASSUMPTIONS, llm_client.MODEL_NAME), unsafe_allow_html=True)
