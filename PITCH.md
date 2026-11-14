# Rotation Compass — Climate-aware crop rotation support from NASA POWER

## 1. The problem
Mekong Delta farmers mostly grow rice after rice. That system is under pressure from:
- longer dry seasons and saline intrusion,
- falling groundwater,
- soil fatigue from monoculture,
- pest cycles that never get broken.

Farmers need a simple way to compare rotations against their local climate record and their own priorities. They do not need a black-box yield forecast.

## 2. What the tool does
1. **Pulls 30+ years of daily NASA POWER data** for any lat/lon. It uses the free API at ~0.5° resolution and these parameters: T2M, T2M_MAX, T2M_MIN, PRECTOTCORR, EVLAND, GWETROOT, GWETTOP, RH2M, ALLSKY_SFC_SW_DWN.
2. **Turns the data into farmer-readable indicators:**
   - growing-season length,
   - frost days,
   - heat-stress days,
   - rain − evaporation water balance,
   - longest dry spell,
   - root-zone soil wetness,
   - the *bare-field erosion window*,
   - trends (linear + Mann-Kendall).
3. **Scores every crop's climate fit per season** using a transparent rule set: temperature 35 %, water 40 %, dry-spell 25 %, plus a season-duration check against `season_days`. The traits come from an 8-crop table fact-checked against FAO I&D 24/56, FAO EcoCrop, IRRI, and WorldVeg guidelines (e.g., 35 °C rice flowering sterility limit and Brassicaceae family tagging).
4. **Scores rotations across 8 curated systems plus auto-generated or custom combinations** on five criteria: climate fit, water saving (irrigation demand beyond 80% of seasonal rain), soil health (N-fixing + bare-month soil cover + root diversity), pest-cycle break (family diversity with consecutive-family penalty), and income.
5. **Lets the farmer filter combinations and adjust priority presets/sliders**, re-ranking live.
6. **Explains every ranking.** Each rotation gets evidence bullets, risks, and "needs local validation" notes.
7. **Shows uncertainty:**
   - P10–P90 ranges across years,
   - a +°C / ±% rain scenario slider,
   - weight sensitivity sweeps,
   - a low-confidence flag when scores are close.

## 3. Method (rule-based, fully explainable)
```
Total score = Σ (weight_i × criterion_i) / Σ weight_i      (criteria scaled 0–100)
Water saving = 100 − scaled irrigation need,
               irrigation need = max(0, crop water need − 0.8 × median seasonal rain)
```
There is no hidden model. Every number traces back to a POWER indicator or a trait-table entry.

## 4. Worked example — Cần Thơ (10.03 N, 105.78 E), 1990–2023
**Local climate**
- Mean temperature 27.3 °C, with no frost risk.
- About 70 days a year above 35 °C. This heat stress matters for rice at flowering.
- The median longest dry spell is about 40 days, in the Jan–Apr dry season.
- Rainfall shows no significant trend (Mann-Kendall p = 0.59).

**Initial 4-strategy baseline snapshot (Cần Thơ, pre-combination expansion)**

| Rank | Rotation | Score |
|---|---|---|
| 1 | Rice → Mung bean → Maize | 71.8 |
| 2 | Rice → Soybean → Vegetables | 71.0 |
| 3 | Rice → Maize | 54.8 |
| 4 | Rice → Rice (baseline) | 46.2 |

*(Note: After expanding to 8 curated rotations + interactive combination pools, fact-checking FAO/IRRI thresholds such as rice 35 °C flowering sterility, and adding consecutive same-family penalties, **Rice–Soybean–Leafy Brassicas** (`Poaceae → Fabaceae → Brassicaceae`, 3 distinct families with zero repeated adjacent families) is designed to avoid the same-family `Maize → Rice` transition penalty. Re-run `streamlit run app.py` to view updated live scores.)*

**Why the baseline ranks last:** dry-season rice needs heavy irrigation, because rain covers only a fraction of its water need. It also fixes no nitrogen, leaves no pest break, and leaves a bare-field window in a wet month.

**Why the top two win:** a legume fixes nitrogen and the dry-season crops need far less water. Three crop families also break the pest cycles.

**Honest flag:** the top two are within 1 point, so the tool marks the result as *low confidence*. The choice between them should come from market access and the farmer's own preference.

**Scenario test:** use the sliders to apply +2 °C and −15 % rain to the historical series. Heat stress rises and the irrigation burden on dry-season rice grows, so the baseline's position gets worse. The legume rotations stay on top.

## 5. Limits we state openly
- POWER data is **modeled and coarse** (~50 km). It is not measured at the farm.
- POWER has **no soil, salinity, pest or market data**. Trait values are generic FAO / extension figures.
- Income is qualitative only.
- Results are a **starting point for a conversation** with extension officers. They are not a prescription.

## 6. Next steps / extensions
- **SoilGrids** for soil texture, pH and organic carbon.
- **SMAP** for higher-resolution soil moisture.
- **MODIS NDVI** to confirm real cropping calendars and bare-field periods.
- **GRACE** for groundwater depletion trends.
- **FAO GAEZ** for crop suitability.
- Local **salinity monitoring** (critical in the Delta).
- Vietnamese-language UI and offline mode for extension workers.

> This tool supports, and does not replace, farmer and expert judgment.
