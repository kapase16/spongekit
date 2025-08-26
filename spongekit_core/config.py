"""
spongekit_core.config
---------------------
Configuration objects (dataclasses) and tiny helpers.

Audience
--------
Hydrologists who can read Python but may not write it every day.

Why this file exists
--------------------
We keep *all* user inputs in one place so the rest of the code can receive
a single `RunConfig` object instead of many separate parameters. This also
makes testing and reproducibility easier.

Units
-----
- Rainfall depth: millimetres (mm)
- Areas: square metres (m²)
- Volumes: cubic metres (m³)

Design choices
--------------
- Use small, explicit dataclasses (easy to read and test).
- Use safe defaults (Amsterdam, 1.0 km tile, 50 mm event).
- Create output folders early to avoid "No such file or directory" errors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

# Type alias: a bounding box in EPSG:4326 degrees -> [W, S, E, N]
BBox = List[float]


# ------------------------
# SuDS presets (simple)
# ------------------------
@dataclass
class RoofPreset:
    """
    Green roof preset (parameters for a *type* of green roof).

    Parameters
    ----------
    name : str
        Short label (e.g., "EXTENSIVE", "INTENSIVE").
    R_mm : float
        Retention/storage capacity in mm. In our simple "bucket" model,
        this is the amount of rain depth the roof can absorb before it
        starts overflowing.
    C_runoff : float
        Runoff coefficient (0..1) applied to *overflow* from the green roof.
        1.0 = all overflow becomes runoff, 0.25 means strong attenuation.
    unit_cost : float
        Capital cost per square metre (currency/m²). Leave units generic
        so you can plug your own currency (e.g., INR, EUR, USD).
    """
    name: str
    R_mm: float
    C_runoff: float
    unit_cost: float


# ------------------------
# Main run configuration
# ------------------------
@dataclass
class RunConfig:
    """
    All inputs needed for a single SpongeKit run.

    Only include what we need *right now*; we can extend later.

    Spatial inputs
    --------------
    place : str
        Place name to geocode via OpenStreetMap (e.g., "Amsterdam, Netherlands").
    tile_km : float
        **Edge length** of a square tile around the place centre (km).
        We keep it small (<= 5 km) so OSM queries are fast.

    Storm
    -----
    storm_mm : float
        Event rainfall depth (mm) when using single-depth mode.

    Scenarios
    ---------
    scenarios : list[float]
        Fractions of total roof area to convert to green roof, 0..1 (e.g., 0.1 = 10%).

    Other
    -----
    C_roof : float
        Baseline impervious roof runoff coefficient (default 0.9).
    crs_projected : int
        Projected CRS EPSG code for area calculations (metres). Default 32633 (UTM for NL).
    bbox : list[float] | None
        If provided (W,S,E,N in degrees), we use this instead of geocoding.
    cache_folder / outputs_folder / map_folder / reports_folder : Path
        Folders where we save intermediate and final outputs.
    """
    # --- spatial ---
    place: str = "Amsterdam, Netherlands"
    tile_km: float = 1.0
    bbox: Optional[BBox] = None
    crs_projected: int = 32633  # UTM zone 33N (metres) works for Amsterdam

    # --- storm ---
    storm_mm: float = 50.0  # single event depth in mm (simple mode)

    # --- scenarios ---
    scenarios: List[float] = field(default_factory=lambda: [0.1, 0.2, 0.3, 0.4, 0.5])

    # --- coefficients / costs ---
    C_roof: float = 0.9  # typical impervious roof runoff coefficient

    # --- folders ---
    cache_folder: Path = Path("cache")
    outputs_folder: Path = Path("outputs")
    map_folder: Path = Path("maps")
    reports_folder: Path = Path("reports")


def ensure_folders(cfg: RunConfig) -> None:
    """
    Create output/cache folders if they do not exist.

    Why:
    - Many later steps (maps, reports, csv) write files.
    - Creating folders early prevents "No such file or directory" errors.

    This function has **no return**; it modifies the filesystem only.
    """
    for p in [cfg.cache_folder, cfg.outputs_folder, cfg.map_folder, cfg.reports_folder]:
        p.mkdir(parents=True, exist_ok=True)


# ------------------------
# Minimal bbox helper
# ------------------------
def square_bbox_around(place: str, tile_km: float) -> BBox:
    """
    Build a small square bbox around a place centre (in degrees, EPSG:4326).

    We use a simple degrees-per-km approximation:
    - ~111 km per degree latitude.
    - For longitude we divide by cos(latitude) to account for convergence.

    This is *good enough* for small tiles (<= 5 km) and avoids pulling
    heavy GIS dependencies here.

    Returns
    -------
    [W, S, E, N] as floats.
    """
    # We import here so the module stays light if someone imports config only.
    import math
    import osmnx as ox

    g = ox.geocode_to_gdf(place)
    c = g.geometry.iloc[0].centroid
    lon, lat = float(c.x), float(c.y)

    half_km = float(tile_km) / 2.0
    dlat = half_km / 111.0
    dlon = half_km / (111.0 * max(0.1, abs(math.cos(math.radians(lat)))))

    W, E = lon - dlon, lon + dlon
    S, N = lat - dlat, lat + dlat
    return [W, S, E, N]


def build_config(
    place: str = "Amsterdam, Netherlands",
    tile_km: float = 1.0,
    storm_mm: float = 50.0,
    bbox: Optional[BBox] = None,
    crs_projected: int = 32633,
) -> RunConfig:
    """
    Convenience constructor with safe defaults.

    - If `bbox` is not given, we compute it from (place, tile_km).
    - We also ensure folders exist.

    Parameters
    ----------
    place : str
        Geocodable place name.
    tile_km : float
        Square tile edge length in kilometres.
    storm_mm : float
        Event depth (mm).
    bbox : list[float] | None
        Optional [W,S,E,N] degrees to override geocoding.
    crs_projected : int
        EPSG code (metres) for area calculations.

    Returns
    -------
    RunConfig
        Ready-to-use configuration object.
    """
    cfg = RunConfig(
        place=place,
        tile_km=float(tile_km),
        storm_mm=float(storm_mm),
        bbox=bbox if bbox is not None else square_bbox_around(place, tile_km),
        crs_projected=int(crs_projected),
    )
    ensure_folders(cfg)
    return cfg
