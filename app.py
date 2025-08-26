"""
app.py — Streamlit UI for SpongeKit (minimal but complete slice)

Audience
--------
Hydrologists who can read Python. Every step is commented with units and intent.

What this app does (end-to-end)
-------------------------------
1) Sidebar inputs: place, tile size, storm (depth mm or hyetograph CSV), green roof params, coverage.
2) Fetch OSM buildings for a small square tile around the place centre (cached to disk).
3) Project buildings to a metre-based CRS and compute roof areas (m²).
4) Run scenarios:
   - Largest-first selection of roofs to meet coverage (10–50% by default).
   - Hydrology: baseline vs green roof (bucket storage + runoff coeff).
   - Costs: capex + opex NPV → lifetime cost and cost per m³ retained.
5) Show results table, two plots, a map preview, CSV download.
6) Generate a PDF report (summary + table + both plots).

Design
------
- SI units: mm (rain), m² (areas), m³ (volumes).
- Simple event model (no ET, no inter-event drainage).
- Streamlit reruns on button clicks, so we store results in st.session_state
  to support "secondary actions" (PDF export) after the main run).
"""

from __future__ import annotations

import traceback
import math

import streamlit as st

# Lightweight imports from our core package (heavy GIS deps are used inside functions)
from spongekit_core.config import build_config, ensure_folders
from spongekit_core.io import load_or_fetch_buildings
from spongekit_core.gis import prepare_buildings
from spongekit_core.scenarios import (
    build_green_roof_scenario_table,
    select_green_roofs_by_fraction,
)
from spongekit_core.version import __version__


# ------------------------------------------------------------
# Page & Sidebar: user inputs
# ------------------------------------------------------------
st.set_page_config(page_title="SpongeKit — Minimal", layout="wide")

st.sidebar.title("SpongeKit v1.0")
st.sidebar.caption(f"Version {__version__}")

# Place and tile
place = st.sidebar.text_input(
    "Place (OSM geocoding)",
    value="Amsterdam, Netherlands",
    help="Example: 'Amsterdam, Netherlands' or 'Pune, India'. OSM will geocode the centre.",
)

tile_km = st.sidebar.slider(
    "Tile size (km, square)",
    min_value=0.5,
    max_value=5.0,
    value=1.0,
    step=0.1,
    help="Edge length of a square around the place centre. Smaller = faster.",
    key="tile_km_slider",
)

# Storm mode: depth or hyetograph CSV
storm_mode = st.sidebar.selectbox(
    "Storm mode",
    options=["depth", "hyetograph"],
    index=0,
    key="storm_mode_select",
    help="Choose 'depth' for a single rainfall depth (mm), or 'hyetograph' to upload a CSV with minutes & mm_per_min.",
)

# Placeholders used later inside run_once()
hyeto = None
hyeto_file = None

if storm_mode == "depth":
    # Simple depth input only in depth mode
    storm_mm = st.sidebar.number_input(
        "Storm depth (mm)",
        min_value=0.0,
        value=50.0,
        step=1.0,
        help="Event rainfall depth used in the simple 'depth' mode.",
        key="storm_depth_input",
    )
else:
    # CSV uploader only in hyetograph mode
    hyeto_file = st.sidebar.file_uploader(
        "Upload hyetograph CSV (minutes, mm_per_min)",
        type=["csv"],
        help="CSV with columns like: minutes,mm_per_min",
        key="hyeto_uploader",
    )
    # Placeholder; actual depth will be computed from the CSV
    storm_mm = 0.0

# Green roof parameters
R_mm = st.sidebar.number_input(
    "Green roof storage R (mm)",
    min_value=0.0,
    value=20.0,
    step=1.0,
    help="Bucket storage depth before overflow; 12–20 mm typical for extensive.",
    key="Rmm_input",
)

Cg = st.sidebar.number_input(
    "Green roof runoff coefficient for overflow (Cg)",
    min_value=0.0,
    max_value=1.0,
    value=0.25,
    step=0.05,
    help="Applied to the overflow depth from the green roof. Lower is better.",
    key="Cg_input",
)

unit_cost = st.sidebar.number_input(
    "Unit CAPEX (currency/m²)",
    min_value=0.0,
    value=150.0,
    step=10.0,
    help="Your currency per square metre (e.g., INR/m², EUR/m²).",
    key="unit_cost_input",
)

# Coverage fractions (0..1)
coverage_opts = [0.10, 0.20, 0.30, 0.40, 0.50]
coverage = st.sidebar.multiselect(
    "Coverage fractions (0..1)",
    options=coverage_opts,
    default=[0.10, 0.20, 0.30],
    help="Fractions of total roof area to convert to green roof (largest-first).",
    key="coverage_multiselect",
)

# Main action button
run_btn = st.sidebar.button("Run", key="run_button")

# Heading
st.title("SpongeKit — Scenario table, plots, map, and PDF")
st.write(
    "This UI fetches OSM buildings for a small tile, computes roof areas, "
    "runs largest-first selection, and shows hydrology + cost metrics. "
    "All units: mm (rain), m² (areas), m³ (volumes)."
)


# ------------------------------------------------------------
# Main action: a single function that runs the pipeline once
# ------------------------------------------------------------
def run_once():
    """
    Execute the minimal pipeline with defensive checks and clear messages.

    Steps
    -----
    1) Build a RunConfig (computes bbox and ensures folders exist).
    2) If hyetograph mode, parse CSV and compute total depth.
    3) Fetch OSM buildings within bbox with caching.
    4) Project to metres and compute area_m2; filter tiny slivers (<10 m²).
    5) Assemble a scenario table for chosen coverage fractions.
    6) Render table, plots, map, CSV download.
    7) Save results into st.session_state so 'Generate PDF' works after reruns.
    """
    # 1) Build config: computes a square bbox around the place centre.
    cfg = build_config(place=place, tile_km=float(tile_km), storm_mm=float(storm_mm))
    ensure_folders(cfg)  # create cache/outputs/maps/reports if missing

    # 2) If hyetograph mode, parse uploaded CSV and compute total depth
    if storm_mode == "hyetograph":
        if hyeto_file is None:
            st.warning("Please upload a hyetograph CSV to run in 'hyetograph' mode.")
            return
        try:
            from spongekit_core.rainfall import parse_hyetograph_csv
            hyeto_local = parse_hyetograph_csv(hyeto_file)  # list of (minute, mm_per_min)
            total_depth_mm = sum(mm for _, mm in hyeto_local)
            st.info(f"Hyetograph parsed: {len(hyeto_local)} steps, total depth ≈ {total_depth_mm:.1f} mm")
            # Reflect the total depth in cfg so downstream messages stay correct
            cfg.storm_mm = float(total_depth_mm)
        except Exception as e:
            st.error(f"Failed to parse hyetograph CSV: {e}")
            return
    else:
        hyeto_local = None  # not used in depth mode

    # Info about bbox/storm
    st.info(
        f"BBox [W,S,E,N]: {[round(x, 6) for x in cfg.bbox]} | "
        f"CRS: EPSG:{cfg.crs_projected} | Storm: {cfg.storm_mm} mm"
    )

    # 3) Buildings (cached after first run)
    with st.spinner("Fetching OSM buildings (cached after first success)..."):
        gdf_raw = load_or_fetch_buildings(cfg.bbox, cfg.cache_folder)
    st.write(f"Raw OSM features: {len(gdf_raw)}")

    # 4) Prepare: project to metres and compute areas
    with st.spinner("Projecting to metres and computing areas..."):
        bldgs = prepare_buildings(gdf_raw, cfg.crs_projected)

    if len(bldgs) == 0:
        st.warning(
            "No polygonal buildings found after preparation. "
            "Try a slightly larger tile or a different place."
        )
        return

    total_area = float(bldgs["area_m2"].sum())
    st.success(f"Prepared buildings: {len(bldgs)} | Total roof area: {total_area:,.1f} m²")

    # 5) Scenario table
    if not coverage:
        st.warning("Please pick at least one coverage fraction in the sidebar.")
        return

    with st.spinner("Running scenarios..."):
        table = build_green_roof_scenario_table(
            bldgs=bldgs,
            P_mm=cfg.storm_mm,
            C_roof=cfg.C_roof,
            R_mm=float(R_mm),
            Cg=float(Cg),
            fracs=sorted(coverage),
            mode=storm_mode,          # depth or hyetograph
            hyeto=hyeto_local,        # parsed hyetograph or None
            unit_cost=float(unit_cost),
        )

    # Prepare a friendly view for the UI (convert fractions to % etc.)
    pretty = table.copy()
    pretty["coverage_%"] = (pretty["coverage_frac"] * 100.0).round(0)

    # Table: pick columns in a narrative order (keep only if present)
    cols = [
        "coverage_%",
        "A_green_m2",
        "V_baseline_m3",
        "V_scenario_m3",
        "retained_m3",
        "reduction_pct",
        "capex",
        "npv_opex",
        "lifetime_total",
        "cost_per_m3",
    ]
    cols = [c for c in cols if c in pretty.columns]

    st.subheader("Scenario results")
    st.dataframe(pretty[cols])

    # 6) Plots and CSV export
    import matplotlib.pyplot as plt

    # --- Plot 1: Runoff vs Coverage ---
    st.subheader("Plot: Scenario runoff vs coverage")
    fig, ax = plt.subplots(figsize=(6, 4))
    x_pct = (table["coverage_frac"] * 100.0).tolist()
    y_runoff = table["V_scenario_m3"].tolist()
    ax.plot(x_pct, y_runoff, marker="o", linewidth=2)
    ax.set_xlabel("Coverage (%)")
    ax.set_ylabel("Runoff volume (m³)")
    ax.set_title("Scenario runoff vs coverage")
    ax.grid(True, linestyle="--", alpha=0.4)
    st.pyplot(fig)

    # --- Plot 2: Cost vs % Reduction (scatter) ---
    st.subheader("Plot: Lifetime cost vs % reduction (best value highlighted)")
    fig2, ax2 = plt.subplots(figsize=(6, 4))
    x_red = table["reduction_pct"].tolist()
    y_cost = table["lifetime_total"].tolist()
    labels = (table["coverage_frac"] * 100.0).round(0).astype(int).tolist()
    ax2.scatter(x_red, y_cost, s=60)
    # Annotate points with coverage %
    for x, y, lab in zip(x_red, y_cost, labels):
        ax2.annotate(f"{lab}%", (x, y), xytext=(5, 5), textcoords="offset points")
    # Highlight best value (min finite cost_per_m3)
    cpms = table["cost_per_m3"].tolist()
    finite_idxs = [i for i, v in enumerate(cpms) if math.isfinite(v)]
    if finite_idxs:
        best_i = min(finite_idxs, key=lambda i: cpms[i])
        ax2.scatter([x_red[best_i]], [y_cost[best_i]], s=120, facecolors="none", edgecolors="red", linewidths=2)
        ax2.annotate("best value", (x_red[best_i], y_cost[best_i]), xytext=(8, -12),
                     textcoords="offset points", color="red")
    ax2.set_xlabel("% reduction")
    ax2.set_ylabel("Lifetime cost (currency)")
    ax2.set_title("Cost vs reduction")
    ax2.grid(True, linestyle="--", alpha=0.4)
    st.pyplot(fig2)

    # --- Map preview: selected roofs for one coverage ---
    st.subheader("Map: selected roofs (largest-first) for chosen coverage")
    cov_choices = (table["coverage_frac"] * 100.0).round(0).astype(int).tolist()
    cov_choice = st.selectbox(
        "Coverage to map (%)",
        options=cov_choices,
        index=min(len(cov_choices) - 1, 0),
        key="coverage_map_select",
    )

    frac_to_map = float(cov_choice) / 100.0
    sel_bldgs, target_area, total_area = select_green_roofs_by_fraction(bldgs, frac_to_map)

    # Render a simple basemap using contextily (optional dependency)
    try:
        import contextily as cx

        # Reproject both layers to EPSG:3857 for web tiles
        g_all = bldgs.to_crs(epsg=3857)
        g_sel = sel_bldgs.to_crs(epsg=3857)

        fig_map, axm = plt.subplots(figsize=(6, 6))
        # All buildings in light gray
        g_all.plot(ax=axm, linewidth=0.2, edgecolor="#cccccc", facecolor="#e6e6e6", alpha=0.6)
        # Selected roofs highlighted
        if len(g_sel) > 0:
            g_sel.plot(ax=axm, linewidth=0.6, edgecolor="#333333", facecolor="#66c2a5", alpha=0.8)

        cx.add_basemap(axm, source=cx.providers.CartoDB.Positron)
        axm.set_axis_off()
        axm.set_title(
            f"Selected roofs for {cov_choice}% coverage\n"
            f"Selected area: {float(g_sel['area_m2'].sum()):,.0f} m² (target: {target_area:,.0f} m²)"
        )
        st.pyplot(fig_map)
    except Exception as e:
        st.warning(
            "Map rendering skipped because a dependency failed. "
            "If you see 'ModuleNotFoundError' for contextily or rasterio, install via:\n"
            "`pip install contextily` (rasterio may need system GDAL, see docs)."
        )
        st.code(str(e))

    # --- CSV Export ---
    st.subheader("Export results")
    csv_bytes = pretty[cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download scenario table as CSV",
        data=csv_bytes,
        file_name="spongekit_scenarios.csv",
        mime="text/csv",
        help="Saves the scenario table to a CSV file you can open in Excel.",
    )

    # ---- Persist last results for later (PDF export after rerun) ----
    # Store only what's needed for the report to be re-generated.
    st.session_state["last_results"] = {
        "cfg": cfg,
        "table": table,
        "fig1": fig,
        "fig2": fig2,
    }

    st.caption(
        "Notes: coverage uses a largest-first selection of roofs. All units: "
        "mm for rainfall, m² for areas, m³ for volumes. Costs use simple CAPEX + OPEX NPV."
    )


# ------------------------------------------------------------
# Run the pipeline when the user clicks "Run"
# ------------------------------------------------------------
if run_btn:
    try:
        run_once()
    except Exception as exc:
        st.error(f"An error occurred: {exc}")
        st.code("".join(traceback.format_exc()), language="text")
else:
    st.info("Set inputs in the sidebar and click Run.")


# ------------------------------------------------------------
# PDF section (outside run_once) — safe across reruns
# ------------------------------------------------------------
st.subheader("PDF report")
if "last_results" in st.session_state:
    from spongekit_core.report import generate_pdf_report
    from pathlib import Path

    # Pull the last computed results from session state
    cfg = st.session_state["last_results"]["cfg"]
    table = st.session_state["last_results"]["table"]
    fig = st.session_state["last_results"]["fig1"]
    fig2 = st.session_state["last_results"]["fig2"]

    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = reports_dir / "spongekit_report.pdf"

    if st.button("Generate PDF"):
        try:
            out_file = generate_pdf_report(
                config=cfg, df=table, fig1=fig, fig2=fig2, out_path=pdf_path
            )
            # Offer the freshly created PDF for download
            with open(out_file, "rb") as f:
                st.download_button(
                    label="Download PDF report",
                    data=f.read(),
                    file_name="spongekit_report.pdf",
                    mime="application/pdf",
                )
            st.success(f"Report created: {out_file}")
        except Exception as e:
            st.error(f"PDF generation failed: {e}")
else:
    st.info("Run a scenario first (click **Run** in the sidebar) to enable PDF export.")