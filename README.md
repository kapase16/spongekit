# SpongeKit v1.0

**SpongeKit** is an open-data scenario tool for **Sustainable Drainage Systems (SuDS)**.  
It helps hydrologists, planners, and students explore how measures like **green roofs** or **permeable pavements** can reduce stormwater runoff using real-world building footprints.

---

##  What it does
- Fetches **building footprints** from OpenStreetMap (or you can upload your own polygons).
- Simulates **storm events** with simple hydrology:
  - Baseline roof runoff (impervious roofs, runoff coefficient `C_roof`).
  - Green roofs (retention storage + reduced runoff coefficient).
  - Permeable pavements.
- Runs scenarios for different coverage levels (e.g., 10–50% of roof area).
- Calculates:
  - Runoff volume (m³)
  - Retained volume (m³)
  - % reduction
  - Costs (CAPEX, OPEX, lifetime NPV)
  - Cost per m³ retained
- Produces results as:
  - Interactive **Streamlit app**
  - Command Line Interface (CLI)
  - Tables, plots, maps
  - Exports to **CSV, PNG, PDF**
  - Optional **SWMM `.inp`** file for model validation (and simulation if `pyswmm` is installed).

---

##  Installation

1. Clone the repository and enter the folder:
   ```bash
   git clone https://github.com/yourusername/spongekit.git
   cd spongekit
   ```

2. Create a virtual environment and activate it:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

##  Usage

### Run the Streamlit web app
```bash
streamlit run app.py
```

This will open a browser interface where you can:
- Choose a place (e.g., Amsterdam)
- Select storm type (depth or hyetograph)
- Pick SuDS scenarios (green roofs / pavements)
- Visualize results (tables, plots, maps)
- Export reports

---

### Run from the Command Line (CLI)

Example: simulate Amsterdam roofs under a **50 mm depth storm**, testing **10%, 20%, and 30% green roof coverage**.

```bash
python cli.py run \\
  --place "Amsterdam" \\
  --tile-km 1.5 \\
  --storm-mm 50 \\
  --roof extensive \\
  --scenarios 0.1 0.2 0.3 \\
  --out outputs/
```

This will generate:
- Results table as CSV
- Maps as PNG
- PDF report
- (Optional) SWMM `.inp` file for validation

---

##  Project Structure

```
spongekit/
├── app.py              # Streamlit web app
├── cli.py              # CLI entry point
├── spongekit_core/     # Core hydrology + GIS functions
├── tests/              # Unit tests
├── docs/               # Documentation
├── requirements.txt    # Dependencies
├── README.md           # Project description
└── LICENSE             # MIT License
```

---

##  Documentation
- [`docs/methods.md`](docs/methods.md) → equations, assumptions, and hydrology details.  
- [`docs/quickstart.md`](docs/quickstart.md) → step-by-step tutorial to run the tool.

---

## ⚖️ License
This project is licensed under the **MIT License** – see the [LICENSE](LICENSE) file for details.
