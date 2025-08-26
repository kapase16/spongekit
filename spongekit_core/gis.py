"""
spongekit_core.gis
------------------
Small GIS helpers: project to local CRS and compute roof areas.
"""

from __future__ import annotations

import warnings


def project_to_local(gdf, epsg: int):
    """
    Project a GeoDataFrame to a projected CRS (metres).

    Parameters
    ----------
    gdf : GeoDataFrame (EPSG:4326 expected)
    epsg : int
        Target CRS EPSG code (e.g., 32633 for UTM zone 33N).

    Returns
    -------
    GeoDataFrame in the target CRS.

    Notes
    -----
    - We import geopandas locally to keep module import fast.
    - If CRS is missing, we assume EPSG:4326 as OSM returns lon/lat.
    """
    import geopandas as gpd

    if getattr(gdf, "crs", None) is None:
        gdf = gdf.set_crs(epsg=4326)

    try:
        return gdf.to_crs(epsg=epsg)
    except Exception as e:
        warnings.warn(f"Projection failed for EPSG:{epsg}. Falling back to EPSG:3857. Error: {e}")
        return gdf.to_crs(epsg=3857)  # Web Mercator as last resort


def prepare_buildings(gdf, epsg: int):
    """
    Clean OSM buildings and compute `area_m2`.

    Steps
    -----
    1) Drop null geometries
    2) Keep Polygon/MultiPolygon only
    3) Project to metre-based CRS
    4) Compute area in m²
    5) Filter out tiny slivers (< 10 m²)
    6) Sort largest-first and reset index

    Returns
    -------
    GeoDataFrame with a new float column 'area_m2'.
    """
    import geopandas as gpd
    from shapely.geometry import Polygon, MultiPolygon

    # 1) Drop nulls
    g = gdf[gdf.geometry.notna()].copy()

    # 2) Keep only surfaces
    g = g[g.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]

    if len(g) == 0:
        # Return empty with expected column for downstream safety
        g["area_m2"] = []
        return g

    # 3) Project to local metres CRS
    gp = project_to_local(g, epsg)

    # 4) Area in m²
    gp["area_m2"] = gp.geometry.area.astype(float)

    # 5) Remove very small polygons (noise)
    gp = gp[gp["area_m2"] > 10.0].copy()

    # 6) Largest-first
    gp = gp.sort_values("area_m2", ascending=False).reset_index(drop=True)

    return gp
