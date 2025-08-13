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
    st.markdown("💸 **Cost Parameters**")
    storm_mm = st.number_input("🌧️ Storm Depth (mm)", value=50.0, step=1.0)

    roof_type = st.selectbox("🟩 Green Roof Type", ["Extensive", "Intensive"])
    preset = EXTENSIVE if roof_type == "Extensive" else INTENSIVE
    default_cost = 150 if roof_type == "Extensive" else 300
    unit_cost = st.number_input("Green Roof Cost ($/m²)", value=default_cost, step=10)


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
        scenarios=[s/100 for s in scenarios],
        save_basemap=save_basemap,
        unit_cost=unit_cost      
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
            
    st.subheader("📉 Runoff Volume vs Green Roof Coverage")
    fig, ax = plt.subplots()
    ax.plot(df["coverage_frac"] * 100, df["runoff_m3"], marker='o')
    ax.set_xlabel("Green Roof Coverage (%)")
    ax.set_ylabel("Runoff Volume (m³)")
    ax.set_title("Impact of Green Roof Coverage on Stormwater Runoff")
    ax.grid(True)

    st.pyplot(fig)
    ax2 = ax.twinx()
    ax2.plot(df["coverage_frac"] * 100, df["reduction_%"], marker='s', color='green', linestyle='--')
    ax2.set_ylabel("Runoff Reduction (%)", color='green')
    
    st.subheader("💰 Cost vs Runoff Reduction")

    fig2, ax = plt.subplots()
    ax.plot(df["cost_usd"].astype(float), df["reduction_%"], marker='o', color='green')
    ax.set_xlabel("Cost (USD)")
    ax.set_ylabel("Runoff Reduction (%)")
    ax.set_title("Cost vs Runoff Benefit")
    ax.grid(True)

    st.pyplot(fig2)

