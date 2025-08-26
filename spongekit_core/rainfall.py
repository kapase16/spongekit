"""
spongekit_core.rainfall
-----------------------
Simple rainfall utilities for SpongeKit.

Audience
--------
Hydrologists who can read Python. We keep the math explicit and the code small.

Units
-----
- Depths in millimetres (mm)
- Time step for hyetograph in minutes

Concept
-------
We use a *bucket* model for SuDS storage:
- The first R_mm of rain is **retained** (stored).
- Any rain beyond R_mm **overflows**.
- No evapotranspiration or inter-event drainage in this simple event model.

Two modes
---------
1) "depth": a single event depth P_mm.
2) "hyetograph": a time series [(minute, mm_per_min), ...] that fills
   the bucket minute-by-minute before any overflow occurs.

Defensive coding
----------------
- Negative inputs are floored at 0.
- Missing hyetograph in "hyetograph" mode falls back to the "depth" logic.
"""

from __future__ import annotations

from typing import List, Tuple

import pandas as pd


def event_result_depths(
    mode: str,
    P_mm: float,
    R_mm: float,
    hyeto: List[Tuple[int, float]] | None = None,
) -> tuple[float, float]:
    """
    Split a storm into **retained depth** and **overflow depth** (both in mm).

    Parameters
    ----------
    mode : {"depth","hyetograph"}
        - "depth": single event depth only uses P_mm.
        - "hyetograph": provide `hyeto` as [(minute, mm_per_min), ...].
    P_mm : float
        Total event depth in mm (used directly in "depth" mode; in
        "hyetograph" it is only used for baseline references).
    R_mm : float
        Storage/retention capacity (mm) of the SuDS (e.g., green roof).
    hyeto : list[(minute, mm_per_min)] | None
        Hyetograph for "hyetograph" mode. Ignored in "depth" mode.

    Returns
    -------
    (retained_mm, overflow_mm) : (float, float)
        Both in millimetres.

    Notes
    -----
    - Hyetograph logic: fill the bucket until capacity is used.
      Any rain **in the same minute** after capacity fills becomes overflow.
    """
    # Defensive floors
    P_mm = max(0.0, float(P_mm))
    R_mm = max(0.0, float(R_mm))

    # --- Mode 1: single depth ---
    if mode == "depth":
        retained = min(P_mm, R_mm)
        overflow = max(0.0, P_mm - R_mm)
        return retained, overflow

    # --- Mode 2: hyetograph (minute-by-minute) ---
    if mode == "hyetograph":
        if not hyeto:
            # If no hyetograph provided, degrade gracefully to "depth" logic
            retained = min(P_mm, R_mm)
            overflow = max(0.0, P_mm - R_mm)
            return retained, overflow

        capacity = R_mm  # remaining storage in the bucket (mm)
        retained_sum = 0.0
        overflow_sum = 0.0

        for minute, mm_per_min in hyeto:
            # Floor any negative intensity to zero (defensive)
            step = max(0.0, float(mm_per_min))

            if capacity > 1e-12:
                # Fill available capacity first
                take = min(step, capacity)
                retained_sum += take
                capacity -= take
                step -= take

            # Any remaining rain in this minute is overflow
            if step > 0.0:
                overflow_sum += step

        # Clamp retained to R_mm (should already be true by construction)
        retained_sum = min(retained_sum, R_mm)
        return retained_sum, overflow_sum

    # Unknown mode -> default to depth logic
    retained = min(P_mm, R_mm)
    overflow = max(0.0, P_mm - R_mm)
    return retained, overflow


def parse_hyetograph_csv(file_like) -> List[Tuple[int, float]]:
    """
    Read a simple CSV hyetograph with columns like:
        minutes,mm_per_min
    or   minute,intensity_mm_per_min

    Parameters
    ----------
    file_like : path or file-like
        Anything that pandas.read_csv can handle.

    Returns
    -------
    list[(minute:int, mm_per_min:float)]

    Errors you might see and how to fix
    -----------------------------------
    - ValueError: missing columns
      -> Ensure columns are named like 'minutes' and 'mm_per_min' (case-insensitive),
         or one of the accepted variants below.
    """
    df = pd.read_csv(file_like)
    # Normalize headers for easy matching
    df.columns = [c.strip().lower() for c in df.columns]

    # Accept common variants
    minute_col = next((c for c in ["minute", "minutes", "time_min", "t_min"] if c in df.columns), None)
    inten_col = next((c for c in ["mm_per_min", "intensity", "intensity_mm_per_min", "mm_min"] if c in df.columns), None)

    if minute_col is None or inten_col is None:
        raise ValueError("Hyetograph must include columns like 'minutes' and 'mm_per_min'.")

    minutes = df[minute_col].astype(int).tolist()
    intens = [max(0.0, float(x)) for x in df[inten_col].fillna(0.0).tolist()]
    return list(zip(minutes, intens))
