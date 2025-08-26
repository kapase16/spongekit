"""
spongekit_core.hydro
--------------------
Event-based hydrology utilities for SpongeKit.

Audience
--------
Hydrologists who can read Python. We keep formulas explicit and use SI units:
- mm for rainfall depth
- m² for areas
- m³ for volumes

What’s here
-----------
1) baseline_runoff:   V_base = (P_mm/1000) * C_roof * A_total
2) scenario_runoff_green_roofs:
   - Split area into green and non-green
   - Green area uses a bucket model (R_mm) and an overflow coefficient Cg
   - Non-green area remains impervious with C_roof
   Returns: (V_scenario_m3, retained_m3 = max(V_base - V_scn, 0))
"""

from __future__ import annotations

from typing import List, Tuple

from .rainfall import event_result_depths


def baseline_runoff(P_mm: float, C_roof: float, A_total_m2: float) -> float:
    """
    Baseline **runoff volume** from impervious roofs.

    Parameters
    ----------
    P_mm : float
        Event depth (mm). If you use a hyetograph elsewhere, pass its total depth here.
    C_roof : float
        Impervious roof runoff coefficient (0..1). Default in config is ~0.9.
    A_total_m2 : float
        Total roof area (m²).

    Returns
    -------
    float
        Runoff volume in cubic metres (m³).

    Formula
    -------
    V = (P_mm / 1000) * C_roof * A_total_m2
    """
    # Defensive checks and clamping
    P_mm = max(0.0, float(P_mm))
    C_roof = min(1.0, max(0.0, float(C_roof)))
    A_total_m2 = max(0.0, float(A_total_m2))

    # Convert mm -> m (divide by 1000), then multiply by area and coefficient
    return P_mm / 1000.0 * C_roof * A_total_m2


def scenario_runoff_green_roofs(
    mode: str,
    P_mm: float,
    R_mm: float,
    C_roof: float,
    Cg: float,
    A_total_m2: float,
    A_green_m2: float,
    hyeto: List[Tuple[int, float]] | None = None,
) -> tuple[float, float]:
    """
    Scenario runoff with a fraction of roofs converted to **green roofs**.

    Parameters
    ----------
    mode : {"depth","hyetograph"}
        - "depth": use P_mm only
        - "hyetograph": provide `hyeto=[(minute, mm_per_min), ...]` as well
    P_mm : float
        Event depth (mm).
    R_mm : float
        Green roof storage (retention) depth (mm) in the bucket model.
    C_roof : float
        Baseline impervious roof runoff coefficient (0..1).
    Cg : float
        Green roof overflow runoff coefficient (0..1). Lower is better.
    A_total_m2 : float
        Total roof area (m²).
    A_green_m2 : float
        Area converted to green roof (m²).
    hyeto : list[(int minute, float mm_per_min)] | None
        Hyetograph when mode=="hyetograph".

    Returns
    -------
    (V_scenario_m3, retained_m3) : (float, float)
        - V_scenario_m3: scenario runoff volume (m³)
        - retained_m3: positive benefit vs baseline (m³), never negative.

    Method
    ------
    1) Compute baseline V_base on the full area with C_roof.
    2) Compute green roof **overflow depth** using the bucket (R_mm) and the chosen mode.
    3) Green runoff = overflow_mm * Cg * A_green (convert mm->m)
    4) Rest runoff = P_mm * C_roof * (A_total - A_green) (convert mm->m)
    5) V_scn = V_green + V_rest
    6) retained = max(V_base - V_scn, 0)
    """
    # --- defensive floors/clamps ---
    P_mm = max(0.0, float(P_mm))
    R_mm = max(0.0, float(R_mm))
    C_roof = min(1.0, max(0.0, float(C_roof)))
    Cg = min(1.0, max(0.0, float(Cg)))
    A_total_m2 = max(0.0, float(A_total_m2))
    A_green_m2 = min(A_total_m2, max(0.0, float(A_green_m2)))

    # 1) Baseline on the full area
    V_base = baseline_runoff(P_mm, C_roof, A_total_m2)

    # 2) Overflow on green area after storage
    retained_mm, overflow_mm = event_result_depths(mode, P_mm, R_mm, hyeto=hyeto)

    # 3) Runoff from green portion (overflow reduced by Cg)
    V_green = overflow_mm / 1000.0 * Cg * A_green_m2

    # 4) Runoff from remaining impervious area
    A_rest = max(0.0, A_total_m2 - A_green_m2)
    V_rest = P_mm / 1000.0 * C_roof * A_rest

    # 5) Total scenario runoff
    V_scn = V_green + V_rest

    # 6) Benefit (never negative)
    retained_m3 = max(0.0, V_base - V_scn)

    return V_scn, retained_m3
def costs(
    A_green_m2: float,
    unit_cost: float,
    opex_rate: float = 0.02,
    years: int = 30,
    discount: float = 0.03,
) -> tuple[float, float, float]:
    """
    Compute simple lifecycle costs for green roofs.

    Parameters
    ----------
    A_green_m2 : float
        Implemented green roof area (m²).
    unit_cost : float
        Capital cost per m² (currency/m²). Use your currency (e.g., INR, EUR).
    opex_rate : float, default 0.02
        Annual O&M cost as a fraction of CAPEX (e.g., 2% of capex per year).
    years : int, default 30
        Analysis horizon in years.
    discount : float, default 0.03
        Discount rate (e.g., 3% per year) to compute NPV of OPEX.

    Returns
    -------
    (capex, npv_opex, lifetime_total)
        capex : float
            Upfront cost in currency.
        npv_opex : float
            Present value of annual O&M costs.
        lifetime_total : float
            capex + npv_opex.

    Notes
    -----
    - OPEX model: each year costs (opex_rate * capex), discounted back with (1+discount)^t
    - Defensive checks prevent divide-by-zero if discount == 0.
    """
    A = max(0.0, float(A_green_m2))
    u = max(0.0, float(unit_cost))
    r = max(0.0, float(opex_rate))
    n = max(1, int(years))
    d = max(0.0, float(discount))

    capex = A * u

    annual_opex = r * capex
    if d > 0.0:
        # NPV of uniform yearly payments: A * [1 - (1 + d)^(-n)] / d
        npv_opex = annual_opex * (1.0 - (1.0 + d) ** (-n)) / d
    else:
        # If discount is zero, NPV is just n * annual cost
        npv_opex = annual_opex * n

    lifetime_total = capex + npv_opex
    return capex, npv_opex, lifetime_total
