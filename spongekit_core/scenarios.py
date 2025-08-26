"""
spongekit_core.scenarios
------------------------
Scenario selection utilities.

Goal of this minimal step
-------------------------
Provide a simple, testable function that:
- takes a table of building footprints with an `area_m2` column
- sorts by area (largest first)
- accumulates areas until a target fraction of the total is met
- returns the selected subset

Why largest-first?
------------------
For a fixed coverage fraction, picking larger roofs first is a common,
defensible heuristic (lower edge losses, simpler maintenance). Later we can
replace this with spatial prioritisation (e.g., near flood hotspots).

Inputs and units
----------------
- Expects a pandas or geopandas DataFrame with a numeric `area_m2` column (m²).
- The function is agnostic to geometry — it only looks at `area_m2`.
"""

from __future__ import annotations

from typing import Tuple

import pandas as pd


def _validate_area_column(df: pd.DataFrame) -> None:
    """
    Internal helper: ensure `area_m2` exists and is valid.

    Raises
    ------
    ValueError: if `area_m2` missing or non-positive.
    """
    if "area_m2" not in df.columns:
        raise ValueError("DataFrame must include an 'area_m2' column in square metres (m²).")
    if not pd.api.types.is_numeric_dtype(df["area_m2"]):
        raise ValueError("'area_m2' must be numeric (float).")
    if float(df["area_m2"].fillna(0).sum()) <= 0.0:
        raise ValueError("'area_m2' total must be positive.")


def select_green_roofs_by_fraction(df: pd.DataFrame, frac: float) -> Tuple[pd.DataFrame, float, float]:
    """
    Select roofs (largest-first) to meet a target coverage fraction.

    Parameters
    ----------
    df : pandas.DataFrame (or GeoDataFrame)
        Must contain a numeric column 'area_m2' in m². Any extra columns are preserved.
    frac : float
        Target coverage fraction (0..1). Example: 0.3 means 30% of total roof area.

    Returns
    -------
    (selected, target_area_m2, total_area_m2)
        selected : DataFrame subset (rows chosen)
        target_area_m2 : float, area required to reach `frac`
        total_area_m2  : float, sum of all areas

    Method
    ------
    1) Sort by area_m2 descending.
    2) Accumulate until cumulative >= target_area_m2.
    3) Return the rows up to that index.

    Defensive checks
    ----------------
    - Clamp `frac` to 0..1.
    - If `frac` is 0, return empty selection.
    - If `frac` is tiny but positive and the largest roof already exceeds target,
      we still select that one (can't split a building).
    """
    # Validate and clamp inputs
    _validate_area_column(df)
    f = max(0.0, min(1.0, float(frac)))

    total = float(df["area_m2"].fillna(0.0).sum())
    target = f * total

    if target <= 0.0:
        # Edge case: 0% coverage -> empty selection
        return df.iloc[0:0].copy(), 0.0, total

    # Sort largest-first and compute cumulative sum
    ordered = df.sort_values("area_m2", ascending=False).reset_index(drop=True)
    csum = ordered["area_m2"].cumsum()

    # Find the first index where cumulative area meets/exceeds the target
    idx = (csum >= target).idxmax()  # idxmax returns first True index

    # Select rows up to and including that index
    selected = ordered.iloc[: idx + 1].copy()

    return selected, float(target), float(total)

def build_green_roof_scenario_table(
    bldgs: pd.DataFrame,
    P_mm: float,
    C_roof: float,
    R_mm: float,
    Cg: float,
    fracs: list[float],
    mode: str = "depth",
    hyeto: list[tuple[int, float]] | None = None,
     unit_cost: float = 150.0,
) -> pd.DataFrame:
    """
    Combine selection + hydrology into a tidy scenario table.

    Parameters
    ----------
    bldgs : DataFrame/GeoDataFrame
        Must contain 'area_m2' (m²) for each roof polygon.
    P_mm : float
        Event rainfall depth (mm), used directly in "depth" mode.
    C_roof : float (0..1)
        Baseline impervious roof runoff coefficient.
    R_mm : float
        Green roof storage depth (mm) for the bucket model.
    Cg : float (0..1)
        Runoff coefficient applied to **overflow** from green roof.
    fracs : list[float]
        Coverage fractions to test (0..1), e.g., [0.1,0.2,0.3].
    mode : {"depth","hyetograph"}
        If "hyetograph", provide `hyeto=[(minute, mm_per_min), ...]`.
    hyeto : list[(int, float)] | None
        Hyetograph for "hyetograph" mode.

    Returns
    -------
    pandas.DataFrame
        Columns:
        - coverage_frac (0..1)
        - A_total_m2
        - A_green_m2
        - V_baseline_m3
        - V_scenario_m3
        - retained_m3
        - reduction_pct (0..100)

    Notes
    -----
    - Areas/volumes are in SI units (m², m³).
    - coverage is implemented as *largest-first* roof selection.
    """
    import pandas as pd
    from .hydro import baseline_runoff, scenario_runoff_green_roofs, costs

    # Defensive: ensure the area column is valid
    _validate_area_column(bldgs)

    # Totals (m²) and baseline (m³)
    A_total = float(bldgs["area_m2"].sum())
    V_base = baseline_runoff(P_mm, C_roof, A_total)

    rows = []
    for f in fracs:
        sel, target, _total = select_green_roofs_by_fraction(bldgs, f)
        A_green = float(sel["area_m2"].sum())

        V_scn, retained = scenario_runoff_green_roofs(
            mode=mode,
            P_mm=P_mm,
            R_mm=R_mm,
            C_roof=C_roof,
            Cg=Cg,
            A_total_m2=A_total,
            A_green_m2=A_green,
            hyeto=hyeto,
        )
        
                # Costing for this scenario
        capex, npv_opex, lifetime_total = costs(
            A_green_m2=A_green,
            unit_cost=unit_cost,
            opex_rate=0.02,   # safe default; adjust as needed
            years=30,
            discount=0.03,
        )

        cost_per_m3 = None
        if retained > 1e-9:
            cost_per_m3 = lifetime_total / retained
        else:
            # Avoid divide-by-zero; leave as None to indicate not meaningful
            cost_per_m3 = float("inf")

        reduction_pct = 0.0
        if V_base > 1e-12:
            reduction_pct = 100.0 * max(0.0, (V_base - V_scn)) / V_base

        rows.append(
            {
                "coverage_frac": float(f),
                "A_total_m2": A_total,
                "A_green_m2": A_green,
                "V_baseline_m3": V_base,
                "V_scenario_m3": V_scn,
                "retained_m3": retained,
                "reduction_pct": reduction_pct,
                "capex": capex,
                "npv_opex": npv_opex,
                "lifetime_total": lifetime_total,
                "cost_per_m3": cost_per_m3,
            }
        )

    return pd.DataFrame(rows).sort_values("coverage_frac").reset_index(drop=True)
