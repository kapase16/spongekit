# 🌱 SpongeKit

**SpongeKit** is an open-source, open-data-based green roof retrofit scenario generator.  
It simulates the impact of various green infrastructure coverage levels on urban rooftops using just OpenStreetMap data — with no proprietary GIS tools required.

---

## 🔍 What it does

- Fetches buildings from OpenStreetMap for any city/tile
- Applies user-defined green roof scenarios (e.g., 10%–100%)
- Simulates simplified runoff reduction for a storm
- Visualizes results as maps (with optional basemaps)
- Outputs CSV results + reproducible metadata
- All through an interactive [Streamlit](https://streamlit.io) app

---

## 🚀 Try it locally

```bash
git clone https://github.com/your-username/spongekit.git
cd spongekit
conda activate spongekit  # or your env
streamlit run app.py

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
