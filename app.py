"""
🌾 CropRotate — NASA POWER Crop Rotation Decision-Support Tool

A transparent, farmer-friendly tool that uses NASA POWER climate data
to help evaluate crop rotation strategies.

Run with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from power_api import fetch_power_data, get_location_info, DEMO_LOCATIONS
from crops import CROP_DB, ROTATIONS, get_crop_table_df, Rotation, RotationSlot
from indicators import (
    growing_season_length, frost_risk, heat_stress,
    monthly_water_balance, dry_spell_analysis,
    soil_wetness_seasonal, bare_field_erosion_risk,
    linear_trend, mann_kendall_trend,
    apply_scenario, indicator_percentile_range,
)
from scoring import (
    score_rotation, compare_rotations, sensitivity_analysis,
    DEFAULT_WEIGHTS, WEIGHT_LABELS,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="🌾 CropRotate — NASA POWER",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .block-container { max-width: 1200px; }
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 10px; padding: 15px; margin: 5px 0;
        border-left: 4px solid #2E86C1;
    }
    .stAlert > div { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sidebar — Location & Settings
# ---------------------------------------------------------------------------
st.sidebar.title("🌍 Location & Settings")

st.sidebar.markdown("### 📍 Select Location")
location_mode = st.sidebar.radio(
    "Choose input method:",
    ["Demo locations", "Custom coordinates"],
    label_visibility="collapsed",
)

if location_mode == "Demo locations":
    loc_name = st.sidebar.selectbox("Location", list(DEMO_LOCATIONS.keys()))
    lat, lon = DEMO_LOCATIONS[loc_name]
else:
    lat = st.sidebar.number_input("Latitude", -90.0, 90.0, 10.03, 0.01)
    lon = st.sidebar.number_input("Longitude", -180.0, 180.0, 105.78, 0.01)
    loc_name = f"Custom ({lat:.2f}, {lon:.2f})"

st.sidebar.markdown("### 📅 Data Range")
col_s, col_e = st.sidebar.columns(2)
start_year = col_s.number_input("Start year", 1984, 2023, 1990, 1)
end_year = col_e.number_input("End year", 1984, 2023, 2023, 1)

st.sidebar.markdown("### 🌡️ Climate Scenario")
st.sidebar.caption("Explore how future changes might shift the results.")
temp_delta = st.sidebar.slider("Temperature change (°C)", -2.0, 4.0, 0.0, 0.5)
rain_pct = st.sidebar.slider("Rainfall change (%)", -30, 30, 0, 5)
rain_factor = 1 + rain_pct / 100


# ---------------------------------------------------------------------------
# Sidebar — Priority Weights
# ---------------------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.markdown("### ⚖️ Your Priorities")
st.sidebar.caption("Drag the sliders to reflect what matters most to you. The tool re-ranks rotations in real time.")

weights = {}
for key, label in WEIGHT_LABELS.items():
    weights[key] = st.sidebar.slider(
        label,
        0.0, 1.0,
        DEFAULT_WEIGHTS[key],
        0.05,
        key=f"w_{key}",
    )

# Normalize display
w_total = sum(weights.values())
if w_total > 0:
    weights_norm = {k: v / w_total for k, v in weights.items()}
else:
    weights_norm = DEFAULT_WEIGHTS


# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------
st.title("🌾 CropRotate")
st.markdown(
    "**A NASA POWER–based crop rotation decision-support tool.**  \n"
    "Compare rotation strategies using 40 years of climate data, "
    "transparent scoring, and your own priorities."
)

# Disclaimer banner
st.info(
    "⚠️ **This tool supports — it does not replace — farmer judgment.**  \n"
    "Data is from NASA POWER (MERRA-2 reanalysis, ~50 km resolution). "
    "It has no soil properties, pest data, or market prices. "
    "Always consult local extension services before changing your rotation.",
    icon="ℹ️",
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Fetching NASA POWER data…", ttl=3600)
def load_data(lat, lon, sy, ey):
    return fetch_power_data(lat, lon, sy, ey)

with st.spinner(f"Loading data for {loc_name}…"):
    try:
        raw_df = load_data(lat, lon, start_year, end_year)
    except Exception as e:
        st.error(f"❌ Failed to fetch POWER data: {e}")
        st.info("Check your internet connection or try a different date range.")
        st.stop()

# Apply scenario
df = apply_scenario(raw_df, temp_delta, rain_factor)

loc_info = get_location_info(lat, lon)
scenario_note = ""
if temp_delta != 0 or rain_pct != 0:
    scenario_note = f"  |  🔮 Scenario: {temp_delta:+.1f} °C, {rain_pct:+d}% rain"

st.caption(
    f"📍 {loc_name} ({lat:.2f}°, {lon:.2f}°)  |  "
    f"📅 {start_year}–{end_year}  |  "
    f"📏 {loc_info['resolution']}{scenario_note}"
)


# ============================= TABS =======================================
tab_overview, tab_indicators, tab_rotations, tab_scoring, tab_sensitivity, tab_guide = st.tabs([
    "📊 Climate Overview",
    "📈 Indicators & Trends",
    "🔄 Rotation Strategies",
    "🏆 Scoring & Ranking",
    "🎚️ Sensitivity Analysis",
    "📖 How to Read This",
])


# ---------------------------------------------------------------------------
# TAB 1: Climate Overview
# ---------------------------------------------------------------------------
with tab_overview:
    st.subheader("Monthly Climate Summary")

    # Monthly aggregates
    monthly = df.groupby(df.index.month).agg(
        T2M_mean=("T2M", "mean"),
        T2M_MAX_mean=("T2M_MAX", "mean"),
        T2M_MIN_mean=("T2M_MIN", "mean"),
        Rain_mean=("PRECTOTCORR", lambda x: x.mean() * 30),  # approx mm/month
        Evap_mean=("EVLAND", lambda x: x.mean() * 30),
        GWETROOT_mean=("GWETROOT", "mean"),
        Solar_mean=("ALLSKY_SFC_SW_DWN", "mean"),
    )
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly.index = month_names

    # Top metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Mean Annual Temp", f"{df['T2M'].mean():.1f} °C")
    col2.metric("Annual Rainfall", f"{df.groupby(df.index.year)['PRECTOTCORR'].sum().median():.0f} mm")
    col3.metric("Mean Solar Radiation", f"{df['ALLSKY_SFC_SW_DWN'].mean():.1f} MJ/m²/day")
    col4.metric("Avg Root-zone Wetness", f"{df['GWETROOT'].mean():.2f}")

    # Temperature chart
    fig_temp = go.Figure()
    fig_temp.add_trace(go.Scatter(
        x=month_names, y=monthly["T2M_MAX_mean"],
        name="Max Temp", line=dict(color="#E74C3C", width=2),
        fill=None,
    ))
    fig_temp.add_trace(go.Scatter(
        x=month_names, y=monthly["T2M_mean"],
        name="Mean Temp", line=dict(color="#F39C12", width=2),
    ))
    fig_temp.add_trace(go.Scatter(
        x=month_names, y=monthly["T2M_MIN_mean"],
        name="Min Temp", line=dict(color="#3498DB", width=2),
        fill="tonexty", fillcolor="rgba(52, 152, 219, 0.1)",
    ))
    fig_temp.update_layout(
        title="Monthly Temperature (°C)",
        yaxis_title="Temperature (°C)",
        height=350, template="plotly_white",
    )
    st.plotly_chart(fig_temp, use_container_width=True)

    # Rainfall vs Evaporation
    c1, c2 = st.columns(2)
    with c1:
        fig_rain = go.Figure()
        fig_rain.add_trace(go.Bar(
            x=month_names, y=monthly["Rain_mean"],
            name="Rainfall", marker_color="#3498DB",
        ))
        fig_rain.add_trace(go.Bar(
            x=month_names, y=monthly["Evap_mean"],
            name="Evaporation", marker_color="#E67E22",
        ))
        fig_rain.update_layout(
            title="Monthly Rainfall vs Evaporation (mm)",
            barmode="group", height=300, template="plotly_white",
        )
        st.plotly_chart(fig_rain, use_container_width=True)

    with c2:
        wb = monthly["Rain_mean"] - monthly["Evap_mean"]
        colors = ["#27AE60" if v >= 0 else "#E74C3C" for v in wb]
        fig_wb = go.Figure(go.Bar(
            x=month_names, y=wb, marker_color=colors,
        ))
        fig_wb.update_layout(
            title="Monthly Water Balance (Rainfall − Evaporation, mm)",
            height=300, template="plotly_white",
        )
        st.plotly_chart(fig_wb, use_container_width=True)

    # Soil Wetness
    fig_sw = go.Figure()
    fig_sw.add_trace(go.Scatter(
        x=month_names, y=monthly["GWETROOT_mean"],
        name="Root-zone", line=dict(color="#1ABC9C", width=2),
    ))
    fig_sw.update_layout(
        title="Monthly Root-zone Soil Wetness (0 = dry, 1 = saturated)",
        yaxis_range=[0, 1], height=280, template="plotly_white",
    )
    st.plotly_chart(fig_sw, use_container_width=True)


# ---------------------------------------------------------------------------
# TAB 2: Indicators & Trends
# ---------------------------------------------------------------------------
with tab_indicators:
    st.subheader("Long-term Climate Indicators")

    # Compute indicators
    gs = growing_season_length(df, 10)
    fr = frost_risk(df, 2)
    hs = heat_stress(df, 35)
    ds = dry_spell_analysis(df)
    wb_monthly = monthly_water_balance(df)

    # Show ranges
    st.markdown("#### Uncertainty Ranges (10th – 90th percentile across years)")
    r1, r2, r3, r4 = st.columns(4)
    gs_range = indicator_percentile_range(gs["growing_days"])
    r1.metric("Growing Season (days)", f"{gs_range['median']:.0f}",
              delta=f"range: {gs_range['p10']:.0f}–{gs_range['p90']:.0f}")

    fr_range = indicator_percentile_range(fr["frost_days"])
    r2.metric("Frost Risk Days/yr", f"{fr_range['median']:.0f}",
              delta=f"range: {fr_range['p10']:.0f}–{fr_range['p90']:.0f}")

    hs_range = indicator_percentile_range(hs["heat_stress_days"])
    r3.metric("Heat Stress Days/yr", f"{hs_range['median']:.0f}",
              delta=f"range: {hs_range['p10']:.0f}–{hs_range['p90']:.0f}")

    ds_range = indicator_percentile_range(ds["max_dry_spell_days"])
    r4.metric("Max Dry Spell (days)", f"{ds_range['median']:.0f}",
              delta=f"range: {ds_range['p10']:.0f}–{ds_range['p90']:.0f}")

    # Trend charts
    st.markdown("#### Trends Over Time")
    trend_indicator = st.selectbox("Select indicator to plot:", [
        "Growing season length",
        "Heat stress days",
        "Frost risk days",
        "Max dry spell length",
        "Annual rainfall",
    ])

    if trend_indicator == "Growing season length":
        trend_data = gs.set_index("year")["growing_days"]
        ylabel = "Days"
    elif trend_indicator == "Heat stress days":
        trend_data = hs.set_index("year")["heat_stress_days"]
        ylabel = "Days"
    elif trend_indicator == "Frost risk days":
        trend_data = fr.set_index("year")["frost_days"]
        ylabel = "Days"
    elif trend_indicator == "Max dry spell length":
        trend_data = ds.set_index("year")["max_dry_spell_days"]
        ylabel = "Days"
    else:
        annual_rain = df.groupby(df.index.year)["PRECTOTCORR"].sum()
        trend_data = annual_rain
        ylabel = "mm"

    # Mann-Kendall
    mk_result = mann_kendall_trend(trend_data)
    lt_result = linear_trend(trend_data)

    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=trend_data.index, y=trend_data.values,
        mode="lines+markers", name=trend_indicator,
        line=dict(color="#2E86C1"),
    ))
    # Add trendline
    if not np.isnan(lt_result.get("slope_per_year", np.nan)):
        x_fit = np.arange(len(trend_data))
        y_fit = lt_result["slope_per_year"] * x_fit + lt_result["intercept"]
        fig_trend.add_trace(go.Scatter(
            x=trend_data.index, y=y_fit,
            mode="lines", name="Linear trend",
            line=dict(color="#E74C3C", dash="dash"),
        ))
    fig_trend.update_layout(
        title=f"{trend_indicator} — {mk_result.get('interpretation', '')}",
        yaxis_title=ylabel, height=350, template="plotly_white",
    )
    st.plotly_chart(fig_trend, use_container_width=True)

    with st.expander("📊 Trend details"):
        c1, c2 = st.columns(2)
        c1.markdown("**Linear regression:**")
        c1.json(lt_result)
        c2.markdown("**Mann-Kendall test:**")
        c2.json(mk_result)


# ---------------------------------------------------------------------------
# TAB 3: Rotation Strategies
# ---------------------------------------------------------------------------
with tab_rotations:
    st.subheader("Rotation Strategies Under Comparison")

    st.markdown("#### 🌿 Crop Trait Reference Table")
    st.dataframe(get_crop_table_df(), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### 🔄 Rotation Calendars")

    for key, rot in ROTATIONS.items():
        with st.expander(f"{'⭐ ' if rot.is_baseline else ''}{rot.name}", expanded=rot.is_baseline):
            st.markdown(f"*{rot.description}*")

            # Calendar heatmap
            cal_data = []
            for slot in rot.slots:
                for m in slot.months:
                    cal_data.append({
                        "month": m,
                        "crop": slot.label or slot.crop.name,
                        "color": slot.crop.color,
                    })

            # Build calendar row
            cal_months = {i: "🟫 Bare" for i in range(1, 13)}
            cal_colors = {i: "#D5D8DC" for i in range(1, 13)}
            for entry in cal_data:
                cal_months[entry["month"]] = entry["crop"]
                cal_colors[entry["month"]] = entry["color"]

            # Visual calendar using plotly
            fig_cal = go.Figure(go.Bar(
                x=month_names,
                y=[1] * 12,
                marker_color=[cal_colors[i] for i in range(1, 13)],
                text=[cal_months[i] for i in range(1, 13)],
                textposition="inside",
                textfont=dict(color="white", size=12),
                hovertext=[cal_months[i] for i in range(1, 13)],
            ))
            fig_cal.update_layout(
                height=100,
                margin=dict(l=0, r=0, t=0, b=0),
                xaxis=dict(showgrid=False),
                yaxis=dict(visible=False),
                showlegend=False,
                template="plotly_white",
            )
            st.plotly_chart(fig_cal, use_container_width=True)

            c1, c2, c3 = st.columns(3)
            c1.metric("Bare months", len(rot.bare_months))
            c2.metric("Crop families", rot.unique_families)
            c3.metric("N-fixing legume", "✅ Yes" if rot.has_legume else "❌ No")

            # Bare-field erosion risk
            if rot.bare_months:
                covered = set(range(1, 13)) - set(rot.bare_months)
                erosion = bare_field_erosion_risk(df, list(covered))
                bare_rain = erosion[erosion["is_bare"]].groupby("month")["rain_mm"].median()
                if not bare_rain.empty:
                    risky = [month_names[m - 1] for m in bare_rain.index if bare_rain[m] > 100]
                    if risky:
                        st.warning(f"⚠️ High erosion risk in bare months with heavy rain: {', '.join(risky)}")
                    else:
                        st.success("Bare months have low rainfall — erosion risk is limited.")


# ---------------------------------------------------------------------------
# TAB 4: Scoring & Ranking
# ---------------------------------------------------------------------------
with tab_scoring:
    st.subheader("🏆 Rotation Ranking")

    # Current weights display
    st.caption("Weights (from sidebar sliders): " + " | ".join(
        f"{WEIGHT_LABELS[k]}: {weights_norm[k]:.0%}" for k in WEIGHT_LABELS
    ))

    # Comparison table
    ranking_df = compare_rotations(ROTATIONS, df, weights_norm)
    st.dataframe(
        ranking_df,
        use_container_width=True,
        column_config={
            "Total Score": st.column_config.ProgressColumn(
                "Total Score", min_value=0, max_value=100, format="%.1f"
            ),
        },
    )

    rot_results = {
        key: score_rotation(rot, df, weights_norm)
        for key, rot in ROTATIONS.items()
    }

    # Radar chart for top rotations
    st.markdown("#### Sub-score Comparison")
    categories = list(WEIGHT_LABELS.values())

    fig_radar = go.Figure()
    for key, rot in ROTATIONS.items():
        result = rot_results[key]
        values = [result["sub_scores"][k][0] for k in WEIGHT_LABELS]
        values.append(values[0])  # close the polygon
        fig_radar.add_trace(go.Scatterpolar(
            r=values,
            theta=categories + [categories[0]],
            name=rot.name,
            fill="toself",
            opacity=0.6,
        ))
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        height=450, template="plotly_white",
        title="Rotation Sub-scores (0–100)",
    )
    st.plotly_chart(fig_radar, use_container_width=True)

    # Detailed evidence for each rotation
    st.markdown("#### 📋 Evidence & Explanation")
    for key, rot in ROTATIONS.items():
        result = rot_results[key]
        with st.expander(f"{rot.name} — Score: {result['total_score']:.1f}/100"):
            for ev_line in result["evidence"]:
                st.markdown(f"- {ev_line}")

            # Sub-score details
            st.markdown("**Sub-score details:**")
            for cat_key, (score, detail) in result["sub_scores"].items():
                st.markdown(f"- **{WEIGHT_LABELS[cat_key]}**: {score}/100")


# ---------------------------------------------------------------------------
# TAB 5: Sensitivity Analysis
# ---------------------------------------------------------------------------
with tab_sensitivity:
    st.subheader("🎚️ How Sensitive Are Rankings to Your Priorities?")
    st.markdown(
        "This shows how the total score for each rotation changes "
        "as one priority weight is swept from 0% to 100% (while the others adjust proportionally)."
    )

    vary = st.selectbox(
        "Vary which priority?",
        list(WEIGHT_LABELS.keys()),
        format_func=lambda k: WEIGHT_LABELS[k],
    )

    sens_df = sensitivity_analysis(ROTATIONS, df, weights_norm, vary, steps=11)

    fig_sens = px.line(
        sens_df, x="weight_value", y="total_score", color="rotation",
        labels={
            "weight_value": f"{WEIGHT_LABELS[vary]} weight",
            "total_score": "Total Score",
            "rotation": "Rotation",
        },
        title=f"Sensitivity: Rankings vs {WEIGHT_LABELS[vary]} weight",
        template="plotly_white",
    )
    fig_sens.update_layout(height=400)
    st.plotly_chart(fig_sens, use_container_width=True)

    # Confidence note
    scores_sorted = ranking_df["Total Score"].values
    if len(scores_sorted) >= 2:
        gap = scores_sorted[0] - scores_sorted[1]
        if gap < 5:
            st.warning(
                f"⚠️ **Low confidence**: The top two rotations are only {gap:.1f} points apart. "
                "Small changes in weights or local conditions could flip the ranking. "
                "Consider field trials before committing."
            )
        elif gap < 15:
            st.info(
                f"ℹ️ The top rotation leads by {gap:.1f} points — a moderate margin. "
                "Verify with local data."
            )
        else:
            st.success(
                f"✅ The top rotation leads by {gap:.1f} points — a strong margin."
            )


# ---------------------------------------------------------------------------
# TAB 6: How to Read This
# ---------------------------------------------------------------------------
with tab_guide:
    st.subheader("📖 How to Read This Tool")

    st.markdown("""
    ### What is this tool?

    **CropRotate** helps you explore which crop rotation might work best for
    your location, based on 40 years of climate data from NASA. It does NOT
    tell you what to plant — it gives you **evidence** to discuss with your
    local extension officer or agronomist.

    ### Key terms explained

    | Term | What it means |
    |------|--------------|
    | **Water Balance** | Rainfall minus evaporation. Positive = water surplus; negative = you may need irrigation. |
    | **Dry Spell** | Consecutive days with less than 1 mm rain. Long dry spells stress crops that need regular water. |
    | **Root-zone Soil Wetness** | How wet the soil is in the root zone (0 = bone dry, 1 = fully saturated). From a NASA model, not a sensor. |
    | **Growing Season** | Days warm enough for a crop to grow (above its base temperature). |
    | **Heat Stress** | Days above a crop's maximum comfortable temperature. Can reduce yields. |
    | **N-fixing** | Some crops (legumes) add nitrogen to the soil, reducing fertilizer needs for the next crop. |
    | **Pest-Cycle Break** | Growing crops from different botanical families disrupts pest and disease buildup. |
    | **Climate-Fit Score** | How well the local temperature and rainfall match what a crop needs (0–100). |
    | **Mann-Kendall** | A statistical test for whether something is trending up, down, or not changing. |

    ### How the scoring works

    1. Each crop is checked against local climate data for the months it would grow.
    2. Each rotation is scored on 5 criteria: climate fit, water saving, soil health, pest break, and income.
    3. **You** set the priority weights with the sliders in the sidebar.
    4. The total score is a weighted average. The ranking updates live as you adjust.

    ### What the data **cannot** tell you

    - **Soil type**: NASA POWER doesn't know if your field is clay, sand, or loam.
    - **Irrigation**: It doesn't know your water access.
    - **Pests & diseases**: No pest pressure data is included.
    - **Market prices**: Income scores are qualitative, not based on real prices.
    - **Resolution**: Data is ~50 km grid, so microclimates are missed.

    > **Always validate with local observation and expert advice.**

    ### Data source

    [NASA POWER](https://power.larc.nasa.gov/) — Prediction of Worldwide Energy
    Resources. Uses MERRA-2 reanalysis. Free and open.

    ### Potential improvements

    If combined with other data, this tool could be much stronger:
    - **SoilGrids** — global soil property maps (texture, organic carbon, pH)
    - **MODIS NDVI** — satellite vegetation greenness for crop monitoring
    - **SMAP** — soil moisture from satellite radar
    - **GRACE** — groundwater depletion trends
    - **FAO GAEZ** — crop suitability maps
    """)


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.caption(
    "🌾 CropRotate v1.0 | Built for the NASA POWER Crop Rotation Challenge | "
    "Data: [NASA POWER](https://power.larc.nasa.gov/) | "
    "This tool supports, not replaces, farmer judgment."
)
