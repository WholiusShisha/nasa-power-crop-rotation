# 🌾 CropRotate — NASA POWER Crop Rotation Decision-Support Tool

A transparent, farmer-friendly tool that uses 40 years of NASA POWER climate
data to help evaluate and compare crop rotation strategies.

Built for the **NASA POWER Crop Rotation Challenge**.

## Quick Start

```bash
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

## What It Does

1. **Fetches** daily climate data (temperature, rainfall, evaporation, soil
   moisture, solar radiation) from the NASA POWER API for any location.
2. **Computes** farmer-readable indicators: growing season, frost risk, heat
   stress, water balance, dry spells, soil wetness trends.
3. **Scores** crop rotation strategies using a weighted, rule-based model
   against 5 criteria: climate fit, water saving, soil health, pest-cycle
   break, and income potential.
4. **Lets the farmer** set priority weights with interactive sliders and
   see rankings update in real time.
5. **Shows uncertainty** via percentile ranges, trend analysis (Mann-Kendall),
   and a climate-change scenario slider (+°C, ±% rainfall).

## Project Structure

| File | Purpose |
|------|---------|
| `app.py` | Streamlit frontend — all tabs and visualizations |
| `power_api.py` | NASA POWER API client with caching |
| `crops.py` | Crop trait table (8 crops) and rotation definitions (4 strategies) |
| `indicators.py` | Climate indicator computation and trend analysis |
| `scoring.py` | Weighted rotation scoring engine with sensitivity analysis |
| `requirements.txt` | Python dependencies |

## Data Source

[NASA POWER](https://power.larc.nasa.gov/) — Prediction of Worldwide Energy
Resources. Uses MERRA-2 reanalysis data from 1981 to near-present at ~0.5°
resolution (~50 km).

## Limitations (stated by design)

- **Coarse resolution**: ~50 km grid; microclimates are missed.
- **Modeled data**: MERRA-2 reanalysis, not ground-station measurements.
- **No soil properties**: Texture, organic matter, pH are not included.
- **No vegetation index**: No NDVI or crop monitoring.
- **Qualitative income**: Market values are categorical, not dollar amounts.
- **No pest/disease data**: Pest-cycle break is based on crop family diversity only.

## Potential Enhancements

Could be combined with:
- **SoilGrids** — global soil property maps
- **MODIS NDVI** — satellite vegetation indices
- **SMAP** — satellite soil moisture
- **GRACE** — groundwater depletion trends
- **FAO GAEZ** — crop suitability maps

## License

Open source for educational and competition use.
