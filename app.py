import streamlit as st
import os
import pandas as pd
import matplotlib.pyplot as plt

# --- Core functions from SpongeKit v0.1 ---
from spongekit_core.v0_1.core import (
    build_config,
    EXTENSIVE,
    INTENSIVE,
    fetch_buildings,
    simulate_scenarios,
    render_maps
)

# --- App layout setup ---
st.set_page_config(layout="wide")
st.title("🌿 SpongeKit MVP — Green Roof Scenario Explorer")

# --- User Inputs ---
with st.sidebar:
    st.header("🧪 Scenario Inputs")
    place = st.text_input("📍 City / Tile Name", value="Amsterdam, Netherlands")
    tile_km = st.slider("📐 Tile Size (km)", 0.5, 5.0, 1.5, 0.5)
    storm_mm = st.number_input("🌧️ Storm Depth (mm)", value=50.0, step=1.0)

    roof_type = st.selectbox("🟩 Green Roof Type", ["Extensive", "Intensive"])
    preset = EXTENSIVE if roof_type == "Extensive" else INTENSIVE

    scenarios = st.multiselect("% Roof Coverage Scenarios", [10, 20, 30, 40, 50], default=[10, 20, 30])
    save_basemap = st.checkbox("🗺️ Show Basemap in Maps", value=True)

    run_button = st.button("🚀 Run Scenarios")

# --- Run Analysis ---
if run_button:
    progress = st.progress(0)
    status = st.empty()

    status.text("⚙️ Building configuration...")
    CONFIG = build_config(
        place=place,
        tile_km=tile_km,
        storm_mm=storm_mm,
        preset=preset,
        scenarios=[s / 100 for s in scenarios],
        save_basemap=save_basemap
    )
    progress.progress(10)

    status.text("📦 Fetching building footprints...")
    buildings = fetch_buildings(CONFIG)
    progress.progress(40)

    status.text("🌱 Simulating green roof scenarios...")
    df = simulate_scenarios(buildings, CONFIG)
    progress.progress(70)

    status.text("🗺️ Rendering scenario maps...")
    map_paths = render_maps(buildings, CONFIG)
    progress.progress(100)

    st.success("✅ Scenario analysis complete!")
    status.empty()

    # --- Display Scenario Table ---
    st.subheader("📊 Scenario Results")
    st.dataframe(df, use_container_width=True)

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download CSV", data=csv_bytes, file_name="spongekit_scenarios.csv")

    # --- Display Map Images ---
    st.subheader("🗺️ Scenario Maps")
    cols = st.columns(3)
    for i, img_path in enumerate(map_paths):
        if os.path.exists(img_path):
            with open(img_path, "rb") as f:
                img_bytes = f.read()
            cols[i % 3].image(img_bytes, caption=os.path.basename(img_path), 
            use_container_width=True)
