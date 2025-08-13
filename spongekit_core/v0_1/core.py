import os
import math
import json
import hashlib
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as cx
import osmnx as ox
import shapely.geometry as sg
from osmnx.features import features_from_bbox
from shapely.geometry import Polygon
from dataclasses import dataclass

# --- Green roof types ---
@dataclass
class RoofPreset:
    name: str
    R_mm: float  # Retention capacity (mm)
    Cg: float    # Runoff coefficient

EXTENSIVE = RoofPreset("extensive", R_mm=12.0, Cg=0.25)
INTENSIVE = RoofPreset("intensive", R_mm=20.0, Cg=0.15)

# --- Config Builder ---
def square_bbox_around(place: str, tile_km: float = 2.0):
    g = ox.geocode_to_gdf(place)
    c = g.geometry.iloc[0].centroid
    lat, lon = float(c.y), float(c.x)
    dlat = (tile_km / 2.0) / 111.0
    dlon = (tile_km / 2.0) / (111.0 * max(0.1, math.cos(math.radians(lat))))
    return [lon - dlon, lat - dlat, lon + dlon, lat + dlat]

def build_config(place="Amsterdam, Netherlands",
                 tile_km=1.5,
                 storm_mm=50.0,
                 preset: RoofPreset = EXTENSIVE,
                 scenarios=(0.10, 0.20, 0.30),
                 save_basemap=True):
    bbox = square_bbox_around(place, tile_km)
    return {
        "place": place,
        "bbox": bbox,
        "tile_km": tile_km,
        "storm_mm": storm_mm,
        "C_roof": 0.9,
        "Cg": preset.Cg,
        "R_mm": preset.R_mm,
        "scenarios": list(scenarios),
        "save_basemap": save_basemap,
        "map_folder": "outputs/maps"
    }

# --- Data fetching ---
def _bbox_key(bbox):
    s = json.dumps([round(v, 6) for v in bbox])
    return hashlib.md5(s.encode()).hexdigest()[:10]

def fetch_buildings_by_bbox(bbox):
    west, south, east, north = bbox
    tags = {"building": True}

    # Create a Shapely polygon for bounding box
    poly = sg.box(west, south, east, north)

    # Use geometry-based fetching (bypasses bbox limit issues)
    return ox.features_from_polygon(poly, tags)
    
def load_or_fetch_buildings(bbox, cache_dir="outputs/cache"):
    os.makedirs(cache_dir, exist_ok=True)
    key = _bbox_key(bbox)
    path = os.path.join(cache_dir, f"buildings_{key}.gpkg")
    if os.path.exists(path):
        return gpd.read_file(path)
    gdf = fetch_buildings_by_bbox(bbox)
    gdf.to_file(path, driver="GPKG")
    return gdf

# --- Geometry preparation ---
def prepare_buildings(gdf):
    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
    gdf = gdf.to_crs(32633)  # Amsterdam UTM zone
    gdf["area_m2"] = gdf.geometry.area
    gdf = gdf[gdf["area_m2"] > 10.0]
    return gdf.sort_values("area_m2", ascending=False).reset_index(drop=True)

# --- Scenario logic ---
def select_green_roofs(bldgs_gdf, frac):
    total = bldgs_gdf["area_m2"].sum()
    needed = frac * total
    sel = bldgs_gdf.copy()
    sel["cum_area"] = sel["area_m2"].cumsum()
    return sel[sel["cum_area"] <= needed].copy()

def estimate_runoff(config, total_area, green_area):
    P = config["storm_mm"]
    R = config["R_mm"]
    Cr = config["C_roof"]
    Cg = config["Cg"]
    runoff_green = max(0.0, P - R) * Cg * green_area
    runoff_rest = P * Cr * (total_area - green_area)
    return (runoff_green + runoff_rest) / 1000.0  # in m³

# --- Step 1: Fetch buildings ---
def fetch_buildings(config):
    os.makedirs(config["map_folder"], exist_ok=True)
    raw = load_or_fetch_buildings(config["bbox"])
    return prepare_buildings(raw)

# --- Step 2: Simulate scenarios ---
def simulate_scenarios(bldgs, config):
    total_area = bldgs["area_m2"].sum()
    records = []

    for frac in config["scenarios"]:
        sel = select_green_roofs(bldgs, frac)
        green_area = sel["area_m2"].sum()
        runoff_m3 = estimate_runoff(config, total_area, green_area)

        records.append({
            "scenario": f"{int(frac * 100)}%",
            "coverage_frac": frac,
            "green_area_m2": round(green_area, 1),
            "total_roof_m2": round(total_area, 1),
            "runoff_m3": round(runoff_m3, 1)
        })

    return pd.DataFrame.from_records(records)

# --- Step 3: Render scenario maps ---
def render_maps(bldgs, config):
    map_paths = []

    for frac in config["scenarios"]:
        sel = select_green_roofs(bldgs, frac)
        b3857 = bldgs.to_crs(3857)
        s3857 = sel.to_crs(3857) if not sel.empty else sel

        fig, ax = plt.subplots(figsize=(7, 7))
        b3857.plot(ax=ax, alpha=0.25, linewidth=0.2, edgecolor="k")
        if not s3857.empty:
            s3857.boundary.plot(ax=ax, linewidth=1.1, color="green")

        if config["save_basemap"]:
            cx.add_basemap(ax, source=cx.providers.CartoDB.Positron, crs=3857)

        ax.set_axis_off()
        ax.set_title(f"Green Roofs — {int(frac * 100)}% coverage")

        fpath = os.path.join(config["map_folder"], f"green_roof_{int(frac * 100)}_bm.png")
        plt.tight_layout()
        plt.savefig(fpath, dpi=250)
        plt.close()
        map_paths.append(fpath)

    return map_paths
