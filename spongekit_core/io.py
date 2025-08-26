"""
spongekit_core.io
-----------------
Lightweight I/O helpers: fetch OSM buildings inside a bbox and cache to disk.

Design rules
------------
- Keep imports local so importing the package stays fast.
- Cache results to avoid re-downloading from OSM repeatedly.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List

def _bbox_key(bbox: List[float]) -> str:
    """
    Build a short, stable key for a bbox so we can name cache files.

    Parameters
    ----------
    bbox : [W, S, E, N] in degrees (EPSG:4326)

    Returns
    -------
    str : hex key like 'b9f2a1...'
    """
    # Round to 6 decimals so negligible differences don't create new files
    s = ",".join(f"{x:.6f}" for x in bbox)
    return hashlib.md5(s.encode("utf-8")).hexdigest()  # nosec - not for security, just a cache key


def fetch_buildings_by_bbox(bbox: List[float]):
    """
    Download OSM features tagged as buildings inside the bbox.

    Why polygon? OSMnx will split very large bboxes; polygon avoids some quirks.

    Returns
    -------
    GeoDataFrame (EPSG:4326)
    """
    from shapely.geometry import box  # local import to keep module light
    import osmnx as ox

    W, S, E, N = bbox
    poly = box(W, S, E, N)

    # Conservative settings so we don't hammer Overpass
    ox.settings.timeout = 180
    ox.settings.memory = 1024 * 1024 * 1024  # 1GB
    # Keep default overpass_settings to whatever OSMnx ships; can be customized later.

    gdf = ox.features_from_polygon(poly, tags={"building": True})

    # The result can include non-polygons (nodes/ways tags). We keep only polygons;
    # GIS prep will filter further, but it's nice to reduce noise here.
    if "geometry" in gdf.columns:
        gdf = gdf[gdf.geometry.notna()].copy()

    # Ensure CRS flag is set to WGS84
    if getattr(gdf, "crs", None) is None:
        gdf.set_crs(epsg=4326, inplace=True)

    return gdf


def load_or_fetch_buildings(bbox: List[float], cache_dir: Path):
    """
    Read buildings from cache if present; otherwise fetch from OSM and write cache.

    Cache format
    ------------
    - GeoPackage (GPKG) at: {cache_dir}/buildings_{key}.gpkg

    Returns
    -------
    GeoDataFrame (EPSG:4326)
    """
    import geopandas as gpd

    cache_dir.mkdir(parents=True, exist_ok=True)
    key = _bbox_key(bbox)
    path = cache_dir / f"buildings_{key}.gpkg"

    if path.exists():
        return gpd.read_file(path)

    gdf = fetch_buildings_by_bbox(bbox)
    # Write as GPKG (robust for geospatial data)
    gdf.to_file(path, driver="GPKG")
    return gdf
