"""
spongekit_core.report
---------------------
Create a simple PDF report using ReportLab.

What this file provides
-----------------------
- generate_pdf_report(config, df, fig1, fig2, out_path) -> str

Inputs
------
- config : RunConfig
    Used to print basic metadata (place, tile, storm depth).
- df : pandas.DataFrame
    Scenario table (one row per coverage fraction).
- fig1, fig2 : matplotlib.figure.Figure
    The plots you want embedded (Runoff vs Coverage, Cost vs Reduction).
- out_path : str | Path
    Where to write the PDF.

Output
------
- Returns the path to the written PDF (as str). Creates parent folders if missing.

Notes
-----
- We rasterize the Matplotlib figures into PNG bytes and place them into the PDF.
- We keep layout simple and robust. This is a “good enough” report for v1.0.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Tuple

# Import kept local so importing spongekit_core.report has minimal heavy deps
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)


def _figure_to_png_bytes(fig) -> BytesIO:
    """
    Convert a Matplotlib Figure to an in-memory PNG.

    We use bytes (not temp files) to keep this cross-platform and simple.
    """
    bio = BytesIO()
    # Tight bounding box reduces whitespace
    fig.savefig(bio, format="png", dpi=200, bbox_inches="tight")
    bio.seek(0)
    return bio


def _plain_language_summary(df) -> str:
    """
    Build a short, plain-language summary paragraph from the scenario table.

    Method
    ------
    - Identify the scenario with the **largest reduction**.
    - Report its coverage, retained volume, and reduction percent.
    - Keep wording simple and non-technical.
    """
    if df is None or len(df) == 0:
        return (
            "This report summarizes a SpongeKit run. No scenarios were computed, "
            "so results are not available for this location and input."
        )

    # Find scenario with maximum reduction
    best = df.sort_values("reduction_pct", ascending=False).iloc[0]
    cov = float(best.get("coverage_frac", 0.0)) * 100.0
    red = float(best.get("reduction_pct", 0.0))
    ret = float(best.get("retained_m3", 0.0))

    return (
        f"This SpongeKit run explores how converting a portion of roofs to green roofs could "
        f"reduce stormwater runoff. Among the scenarios tested, the largest reduction was "
        f"approximately {red:,.1f}% at a coverage of about {cov:,.0f}% of total roof area, "
        f"retaining around {ret:,.0f} cubic metres of event runoff."
    )


def generate_pdf_report(config, df, fig1, fig2, out_path) -> str:
    """
    Create a concise PDF report containing:
    - Title + metadata
    - Plain-language summary
    - Scenario table
    - Two figures (the ones you pass in)

    Parameters
    ----------
    config : RunConfig
        Holds place name, tile size, storm depth, etc.
    df : pandas.DataFrame
        Scenario results table (must include coverage_frac, retained_m3, etc.).
    fig1, fig2 : matplotlib.figure.Figure
        Figures to embed. The app passes the line plot and the scatter.
    out_path : str | Path
        File path for the PDF.

    Returns
    -------
    str
        The absolute path to the created PDF.

    Errors and how to handle
    ------------------------
    - If ReportLab cannot write (e.g., folder missing), we create the parent folder.
    - If the table is very wide, we select a useful subset of columns to fit the page.
    """
    # Ensure parent folders exist
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Prepare the document
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        title="SpongeKit Scenario Report",
        author="SpongeKit",
    )
    styles = getSampleStyleSheet()
    story = []

    # Title
    title = f"SpongeKit Scenario Report – {config.place}"
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 0.3 * cm))

    # Metadata
    meta = (
        f"Tile size: {config.tile_km:.2f} km | "
        f"Storm depth: {config.storm_mm:.1f} mm | "
        f"CRS: EPSG:{config.crs_projected} | "
        f"BBox [W,S,E,N]: {[round(x, 5) for x in (config.bbox or [])]}"
    )
    story.append(Paragraph(meta, styles["Normal"]))
    story.append(Spacer(1, 0.4 * cm))

    # Summary paragraph
    story.append(Paragraph("Summary", styles["Heading2"]))
    story.append(Paragraph(_plain_language_summary(df), styles["BodyText"]))
    story.append(Spacer(1, 0.5 * cm))

    # Scenario table (select readable columns)
    story.append(Paragraph("Scenario Table", styles["Heading2"]))

    # Choose a compact set of columns for A4 width
    cols = [
        "coverage_frac",
        "A_green_m2",
        "V_baseline_m3",
        "V_scenario_m3",
        "retained_m3",
        "reduction_pct",
        "lifetime_total",
        "cost_per_m3",
    ]
    cols = [c for c in cols if c in df.columns]

    # Build table data with headers
    data = [ [c.replace("_", " ").title() for c in cols] ]
    for _, row in df.sort_values("coverage_frac").iterrows():
        data.append([row[c] for c in cols])

    tbl = Table(data, hAlign="LEFT")
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6e6e6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f7")]),
            ]
        )
    )
    story.append(tbl)
    story.append(Spacer(1, 0.6 * cm))

    # Figures
    story.append(Paragraph("Figures", styles["Heading2"]))
    if fig1 is not None:
        png1 = _figure_to_png_bytes(fig1)
        story.append(Image(png1, width=16 * cm, height=9 * cm))
        story.append(Spacer(1, 0.4 * cm))
    if fig2 is not None:
        png2 = _figure_to_png_bytes(fig2)
        story.append(Image(png2, width=16 * cm, height=9 * cm))
        story.append(Spacer(1, 0.4 * cm))

    # Build the document
    doc.build(story)

    return str(out_path.resolve())
