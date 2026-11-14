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
from crops import (
    CROP_DB, ROTATIONS, get_crop_table_df,
    Rotation, RotationSlot, generate_rotation_combinations,
)
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
WEIGHT_PRESETS = {
    "⚖️ Balanced": DEFAULT_WEIGHTS,
    "💧 Water Crisis": {"climate_fit": 0.25, "water_saving": 0.45, "soil_health": 0.15, "pest_break": 0.05, "income": 0.10},
    "🌱 Soil Health": {"climate_fit": 0.20, "water_saving": 0.15, "soil_health": 0.40, "pest_break": 0.15, "income": 0.10},
    "💰 Max Income": {"climate_fit": 0.20, "water_saving": 0.10, "soil_health": 0.10, "pest_break": 0.10, "income": 0.50},
    "🛡️ Climate Safe": {"climate_fit": 0.45, "water_saving": 0.25, "soil_health": 0.15, "pest_break": 0.10, "income": 0.05},
}


def _apply_weight_preset(preset: dict):
    for k, v in preset.items():
        st.session_state[f"w_{k}"] = float(v)


for key in WEIGHT_LABELS:
    if f"w_{key}" not in st.session_state:
        st.session_state[f"w_{key}"] = float(DEFAULT_WEIGHTS[key])

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚖️ Your Priorities")
st.sidebar.caption("Pick a quick preset or drag sliders to re-rank rotations live.")

preset_cols = st.sidebar.columns(2)
for idx, (p_label, p_weights) in enumerate(WEIGHT_PRESETS.items()):
    preset_cols[idx % 2].button(
        p_label,
        key=f"preset_{idx}",
        on_click=_apply_weight_preset,
        args=(p_weights,),
        use_container_width=True,
    )

weights = {}
for key, label in WEIGHT_LABELS.items():
    weights[key] = st.sidebar.slider(
        label,
        min_value=0.0,
        max_value=1.0,
        step=0.05,
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

    # Temperature chart with reference rice thresholds from CROP_DB
    rice_ref = CROP_DB["rice"]
    fig_temp = go.Figure()
    fig_temp.add_hrect(
        y0=rice_ref.temp_opt_low, y1=rice_ref.temp_opt_high,
        fillcolor="rgba(39, 174, 96, 0.08)", line_width=0,
        annotation_text=f"Rice optimal ({rice_ref.temp_opt_low}–{rice_ref.temp_opt_high} °C)",
        annotation_position="top left",
    )
    fig_temp.add_hline(
        y=rice_ref.temp_max, line_dash="dot", line_color="#C0392B",
        annotation_text=f"Rice heat limit ({rice_ref.temp_max} °C)",
        annotation_position="top right",
    )
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
        title="Monthly Temperature (°C) vs Rice Reference Thresholds",
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

    ref_crop_key = st.selectbox(
        "Reference crop thresholds (from Crop Trait Table):",
        list(CROP_DB.keys()),
        index=0,
        format_func=lambda k: CROP_DB[k].name,
        key="ind_ref_crop",
    )
    ref_crop = CROP_DB[ref_crop_key]
    st.caption(
        f"Using **{ref_crop.name}** thresholds — "
        f"Base min (T2M ≥ {ref_crop.temp_min} °C), "
        f"Cold/chilling risk (T2M_MIN ≤ {ref_crop.temp_min} °C), "
        f"Optimal (T2M {ref_crop.temp_opt_low}–{ref_crop.temp_opt_high} °C), "
        f"Heat limit (T2M_MAX ≥ {ref_crop.temp_max} °C), "
        f"Cycle ({ref_crop.season_days[0]}–{ref_crop.season_days[1]} days)."
    )

    # Compute indicators using reference crop traits
    gs = growing_season_length(df, ref_crop.temp_min)
    fr = frost_risk(df, ref_crop.temp_min)
    hs = heat_stress(df, ref_crop.temp_max)
    ds = dry_spell_analysis(df)
    wb_monthly = monthly_water_balance(df)

    # Show ranges
    st.markdown("#### Uncertainty Ranges (10th – 90th percentile across years)")
    r1, r2, r3, r4 = st.columns(4)
    gs_range = indicator_percentile_range(gs["growing_days"])
    r1.metric("Growing Season (days)", f"{gs_range['median']:.0f}",
              delta=f"range: {gs_range['p10']:.0f}–{gs_range['p90']:.0f}")

    fr_range = indicator_percentile_range(fr["frost_days"])
    r2.metric(f"Chilling Days/yr (≤{ref_crop.temp_min}°C)", f"{fr_range['median']:.0f}",
              delta=f"range: {fr_range['p10']:.0f}–{fr_range['p90']:.0f}")

    hs_range = indicator_percentile_range(hs["heat_stress_days"])
    r3.metric(f"Heat Stress Days/yr (≥{ref_crop.temp_max}°C)", f"{hs_range['median']:.0f}",
              delta=f"range: {hs_range['p10']:.0f}–{hs_range['p90']:.0f}")

    ds_range = indicator_percentile_range(ds["max_dry_spell_days"])
    r4.metric("Max Dry Spell (days)", f"{ds_range['median']:.0f}",
              delta=f"range: {ds_range['p10']:.0f}–{ds_range['p90']:.0f}")

    # Trend charts
    st.markdown("#### Trends Over Time")
    trend_indicator = st.selectbox("Select indicator to plot:", [
        "Growing season length",
        "Heat stress days",
        "Cold / chilling risk days",
        "Max dry spell length",
        "Annual rainfall",
    ])

    if trend_indicator == "Growing season length":
        trend_data = gs.set_index("year")["growing_days"]
        ylabel = "Days"
    elif trend_indicator == "Heat stress days":
        trend_data = hs.set_index("year")["heat_stress_days"]
        ylabel = "Days"
    elif trend_indicator == "Cold / chilling risk days":
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

    with st.expander("🔬 Fact-Check & Agronomic Sources"):
        st.markdown("""
        Trait thresholds were checked against **FAO Irrigation & Drainage Papers 24 & 56**, **FAO EcoCrop**, **IRRI**, and **WorldVeg** guidelines:
        - **Rice heat stress (35 °C):** IRRI identifies 35 °C daily max at flowering (anthesis) as the critical threshold for spikelet sterility (not 40 °C).
        - **Field water vs. crop ETc:** Rice crop evapotranspiration ($ET_c$) is ~500–700 mm, while total field water requirement including land puddling and percolation reaches **800–1,300 mm**. Upland seasonal crop water needs align with FAO 24/56: Maize 500–800 mm, Soybean 450–700 mm, Peanut 500–700 mm, Sweet Potato 400–675 mm.
        - **Mung bean base temperature & roots:** Chilling-sensitive tropical legume (`temp_min` ~15 °C, not 10 °C) with a **medium** taproot (0.5–1.0 m), consistent with high drought tolerance.
        - **Botanical family classification:** Leafy vegetables are modeled specifically as **Leafy Brassicas (*Brassicaceae*)** rather than a generic mixed label so pest-cycle break scoring reflects real family diversity.
        """)

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
    st.subheader("🏆 Interactive Rotation Ranking")

    # Current weights display
    st.caption("Weights (from sidebar sliders): " + " | ".join(
        f"{WEIGHT_LABELS[k]}: {weights_norm[k]:.0%}" for k in WEIGHT_LABELS
    ))

    # --- Combination pool controls ---
    if "custom_rotations" not in st.session_state:
        st.session_state["custom_rotations"] = {}

    st.markdown("#### 🧩 Combination Pool")
    pcol1, pcol2 = st.columns(2)
    include_curated = pcol1.checkbox(
        f"Include {len(ROTATIONS)} curated rotations",
        value=True,
        key="pool_curated",
    )
    include_autogen = pcol2.checkbox(
        "Auto-generate 2-crop & 3-crop combinations",
        value=True,
        key="pool_autogen",
    )

    autogen_rotations = {}
    if include_autogen:
        with st.expander("⚙️ Configure Auto-Generated Crop Combinations", expanded=False):
            g_t1, g_t2 = st.columns(2)
            gen_2crop = g_t1.checkbox("Include 2-crop combos (Wet + Dry)", value=True, key="gen_2crop")
            gen_3crop = g_t2.checkbox("Include 3-crop combos (Wet + Gap + Dry)", value=True, key="gen_3crop")

            c_wet, c_gap, c_dry = st.columns(3)
            all_crop_keys = list(CROP_DB.keys())
            wet_choices = c_wet.multiselect(
                "Wet season (Jun–Oct / Jun–Sep)",
                all_crop_keys,
                default=["rice"],
                format_func=lambda k: CROP_DB[k].name,
                key="gen_wet",
            )
            gap_choices = c_gap.multiselect(
                "Cool / Gap slot (Oct–Dec, 3-crop)",
                all_crop_keys,
                default=["soybean", "mung_bean", "vegetables"],
                format_func=lambda k: CROP_DB[k].name,
                key="gen_gap",
            )
            dry_choices = c_dry.multiselect(
                "Dry season (Jan–Apr / Dec–Mar)",
                all_crop_keys,
                default=["rice_dry", "maize", "mung_bean", "sweet_potato", "peanut", "vegetables"],
                format_func=lambda k: CROP_DB[k].name,
                key="gen_dry",
            )
            autogen_rotations = generate_rotation_combinations(
                wet_choices, gap_choices, dry_choices,
                include_2crop=gen_2crop,
                include_3crop=gen_3crop,
            )

    # --- Custom rotation builder ---
    with st.expander("➕ Custom Rotation Builder", expanded=False):
        n_custom_slots = st.radio(
            "Number of crops per year",
            [2, 3],
            horizontal=True,
            key="cust_n_slots",
        )
        custom_name_input = st.text_input(
            "Rotation name (leave blank to auto-name)",
            key="cust_name",
        )
        default_slot_crops = ["rice", "soybean", "maize"]
        default_slot_starts = [6, 10, 1]
        default_slot_ends = [9, 12, 4]
        crop_keys_list = list(CROP_DB.keys())

        built_slots = []
        slot_cols = st.columns(n_custom_slots)
        for idx, scol in enumerate(slot_cols):
            with scol:
                st.markdown(f"**Crop {idx + 1}**")
                ck = scol.selectbox(
                    "Crop",
                    crop_keys_list,
                    index=crop_keys_list.index(default_slot_crops[idx]),
                    format_func=lambda k: CROP_DB[k].name,
                    key=f"cust_crop_{idx}",
                )
                sm = scol.selectbox(
                    "Start month",
                    list(range(1, 13)),
                    index=default_slot_starts[idx] - 1,
                    format_func=lambda m: month_names[m - 1],
                    key=f"cust_start_{idx}",
                )
                em = scol.selectbox(
                    "End month",
                    list(range(1, 13)),
                    index=default_slot_ends[idx] - 1,
                    format_func=lambda m: month_names[m - 1],
                    key=f"cust_end_{idx}",
                )
                built_slots.append(RotationSlot(ck, sm, em, label=CROP_DB[ck].name))

        used_months = [m for s in built_slots for m in s.months]
        if len(used_months) != len(set(used_months)):
            st.warning("Selected crop windows overlap in one or more months.")

        bcol1, bcol2 = st.columns(2)
        if bcol1.button("Add Custom Rotation", key="add_custom_btn", use_container_width=True):
            auto_label = " → ".join(CROP_DB[s.crop_key].name.split(" (")[0] for s in built_slots)
            final_name = (custom_name_input.strip() or f"{auto_label} [Custom]")
            existing_names = (
                {r.name for r in ROTATIONS.values()}
                | {r.name for r in autogen_rotations.values()}
                | {r.name for r in st.session_state["custom_rotations"].values()}
            )
            if final_name in existing_names:
                final_name = f"{final_name} ({len(st.session_state['custom_rotations']) + 1})"
            ckey = f"custom_{len(st.session_state['custom_rotations']) + 1}_{len(built_slots)}"
            while ckey in st.session_state["custom_rotations"]:
                ckey = f"{ckey}_x"
            st.session_state["custom_rotations"][ckey] = Rotation(
                name=final_name,
                description="User-defined custom rotation.",
                slots=built_slots,
            )
            if "compare_select" in st.session_state:
                st.session_state["compare_select"] = list(
                    dict.fromkeys([final_name] + st.session_state["compare_select"])
                )
            st.success(f"Added custom rotation: {final_name}")

        if st.session_state["custom_rotations"]:
            if bcol2.button("🗑️ Clear Custom Rotations", key="clear_custom_btn", use_container_width=True):
                st.session_state["custom_rotations"] = {}
                st.rerun()
            st.caption(
                "Saved custom rotations: "
                + ", ".join(r.name for r in st.session_state["custom_rotations"].values())
            )

    # --- Assemble unique rotation pool ---
    active_rotations = {}
    curated_2sigs = set()
    curated_3sigs = set()

    if include_curated:
        for k, rot in ROTATIONS.items():
            active_rotations[k] = rot
            if len(rot.slots) == 2:
                curated_2sigs.add(tuple(sorted(s.crop_key for s in rot.slots)))
            elif len(rot.slots) == 3:
                curated_3sigs.add(tuple(s.crop_key for s in rot.slots))

    for k, rot in st.session_state["custom_rotations"].items():
        active_rotations[k] = rot

    if include_autogen:
        for k, rot in autogen_rotations.items():
            if len(rot.slots) == 2 and tuple(sorted(s.crop_key for s in rot.slots)) in curated_2sigs:
                continue
            if len(rot.slots) == 3 and tuple(s.crop_key for s in rot.slots) in curated_3sigs:
                continue
            active_rotations[k] = rot

    slot_cache = {}
    rot_results_by_name = {}
    rot_obj_by_name = {}
    ranking_df = pd.DataFrame()
    filtered_df = pd.DataFrame()
    filtered_names = []
    selected_names = []

    if not active_rotations:
        st.warning("Select curated rotations, auto-generated combinations, or add a custom rotation.")
    else:
        ranking_df = compare_rotations(active_rotations, df, weights_norm, slot_cache=slot_cache)
        for rot in active_rotations.values():
            rot_obj_by_name[rot.name] = rot
            rot_results_by_name[rot.name] = score_rotation(rot, df, weights_norm, slot_cache=slot_cache)

        # --- Interactive Filters ---
        st.markdown("#### 🔍 Filter Ranked Combinations")
        f1, f2, f3, f4 = st.columns(4)
        sys_len = f1.radio("System length", ["All", "2 crops/yr", "3 crops/yr"], key="flt_len")
        req_legume = f2.checkbox("Require N-fixing legume", value=False, key="flt_legume")
        min_families = f3.slider("Min crop families", 1, 3, 1, key="flt_fams")
        irr_ceil = max(int(ranking_df["Est. Irrigation (mm)"].max()), 100)
        irr_ceil = ((irr_ceil + 49) // 50) * 50  # align cleanly to step=50
        prev_ceil = st.session_state.get("_prev_irr_ceil")
        if "flt_irr" not in st.session_state or st.session_state["flt_irr"] > irr_ceil or st.session_state["flt_irr"] == prev_ceil:
            st.session_state["flt_irr"] = irr_ceil
        st.session_state["_prev_irr_ceil"] = irr_ceil
        max_irr = f4.slider(
            "Max est. irrigation (mm/yr)",
            0, irr_ceil, step=50, key="flt_irr",
        )

        fc1, fc2 = st.columns(2)
        must_crops = fc1.multiselect(
            "Must include crops",
            list(CROP_DB.keys()),
            format_func=lambda k: CROP_DB[k].name,
            key="flt_must",
        )
        ban_crops = fc2.multiselect(
            "Exclude crops",
            list(CROP_DB.keys()),
            format_func=lambda k: CROP_DB[k].name,
            key="flt_ban",
        )

        mask = pd.Series(True, index=ranking_df.index)
        if sys_len == "2 crops/yr":
            mask &= ranking_df["Crops/yr"] == 2
        elif sys_len == "3 crops/yr":
            mask &= ranking_df["Crops/yr"] == 3
        if req_legume:
            mask &= ranking_df["N-Fix"] == "Yes"
        mask &= ranking_df["Families"] >= min_families
        mask &= ranking_df["Est. Irrigation (mm)"] <= max_irr
        if must_crops:
            must_set = set(must_crops)
            mask &= ranking_df["Rotation"].apply(
                lambda n: must_set.issubset({s.crop_key for s in rot_obj_by_name[n].slots})
            )
        if ban_crops:
            ban_set = set(ban_crops)
            mask &= ranking_df["Rotation"].apply(
                lambda n: ban_set.isdisjoint({s.crop_key for s in rot_obj_by_name[n].slots})
            )

        filtered_df = ranking_df[mask]
        filtered_names = list(filtered_df["Rotation"])
        st.caption(f"Showing **{len(filtered_df)}** of **{len(ranking_df)}** combinations.")

        st.dataframe(
            filtered_df,
            use_container_width=True,
            column_config={
                "Total Score": st.column_config.ProgressColumn(
                    "Total Score", min_value=0, max_value=100, format="%.1f"
                ),
                "Est. Irrigation (mm)": st.column_config.NumberColumn(
                    "Est. Irrigation (mm)", format="%d mm"
                ),
            },
        )

        if filtered_df.empty:
            st.info("No combinations match the current filters. Relax a filter above to compare strategies.")
        else:
            # --- Stacked Weighted Contribution Bar Chart ---
            st.markdown("#### 📊 Weighted Score Breakdown (Top Filtered Combinations)")
            top_n = min(12, len(filtered_df))
            top_names = list(filtered_df["Rotation"].iloc[:top_n])
            fig_contrib = go.Figure()
            for cat_key, cat_label in WEIGHT_LABELS.items():
                fig_contrib.add_trace(go.Bar(
                    name=cat_label,
                    y=top_names,
                    x=[
                        round(rot_results_by_name[name]["sub_scores"][cat_key][0] * weights_norm[cat_key], 1)
                        for name in top_names
                    ],
                    orientation="h",
                ))
            fig_contrib.update_layout(
                barmode="stack",
                yaxis=dict(autorange="reversed"),
                xaxis_title="Weighted points contributing to Total Score",
                height=max(300, 32 * top_n + 120),
                template="plotly_white",
                title=f"Top {top_n} Combinations — Contribution by Priority",
            )
            st.plotly_chart(fig_contrib, use_container_width=True)

            # --- Head-to-Head Multiselect for Radar & Evidence ---
            default_cmp = filtered_names[:min(4, len(filtered_names))]
            if "compare_select" not in st.session_state:
                st.session_state["compare_select"] = default_cmp
            else:
                valid_cmp = [x for x in st.session_state["compare_select"] if x in filtered_names]
                st.session_state["compare_select"] = valid_cmp if valid_cmp else default_cmp

            st.markdown("#### 🎯 Head-to-Head Comparison")
            selected_names = st.multiselect(
                "Select combinations to overlay on the Radar Chart & inspect evidence",
                options=filtered_names,
                key="compare_select",
            )

            categories = list(WEIGHT_LABELS.values())
            fig_radar = go.Figure()
            for name in selected_names:
                result = rot_results_by_name[name]
                values = [result["sub_scores"][k][0] for k in WEIGHT_LABELS]
                values.append(values[0])  # close the polygon
                fig_radar.add_trace(go.Scatterpolar(
                    r=values,
                    theta=categories + [categories[0]],
                    name=name,
                    fill="toself",
                    opacity=0.55,
                ))
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                height=450, template="plotly_white",
                title="Rotation Sub-scores (0–100)",
            )
            st.plotly_chart(fig_radar, use_container_width=True)

            # Detailed evidence for selected combinations
            st.markdown("#### 📋 Evidence & Explanation")
            rank_lookup = {row["Rotation"]: idx for idx, row in filtered_df.iterrows()}
            for name in selected_names:
                result = rot_results_by_name[name]
                rank_num = rank_lookup.get(name, "?")
                with st.expander(f"#{rank_num} {name} — Score: {result['total_score']:.1f}/100"):
                    for ev_line in result["evidence"]:
                        st.markdown(f"- {ev_line}")

                    st.markdown("**Sub-score details:**")
                    for cat_key, (score, _) in result["sub_scores"].items():
                        st.markdown(f"- **{WEIGHT_LABELS[cat_key]}**: {score}/100")

                    st.markdown("**Per-crop climate & water breakdown:**")
                    water_det = result["sub_scores"]["water_saving"][1]
                    for slot_label, fit in result["sub_scores"]["climate_fit"][1].items():
                        w_note = water_det.get(slot_label, "")
                        st.markdown(
                            f"- *{slot_label}*: climate fit **{fit['overall']}/100** "
                            f"(temp {fit['temp_score']}, rain {fit['water_score']}, dry-spell {fit['dry_spell_score']})"
                            + (f" — {w_note}" if w_note else "")
                        )


# ---------------------------------------------------------------------------
# TAB 5: Sensitivity Analysis
# ---------------------------------------------------------------------------
with tab_sensitivity:
    st.subheader("🎚️ How Sensitive Are Rankings to Your Priorities?")
    st.markdown(
        "This shows how the total score for each rotation changes "
        "as one priority weight is swept from 0% to 100% (while the others adjust proportionally)."
    )

    if ranking_df.empty:
        st.info("Enable or add at least one rotation in the Scoring & Ranking tab.")
    else:
        vary = st.selectbox(
            "Vary which priority?",
            list(WEIGHT_LABELS.keys()),
            format_func=lambda k: WEIGHT_LABELS[k],
        )

        # Plot head-to-head picks (or top 6 filtered) plus baseline to keep chart readable
        baseline_names = [r.name for r in active_rotations.values() if r.is_baseline]
        base_pick = selected_names if selected_names else list(ranking_df["Rotation"].iloc[:6])
        sens_names = list(dict.fromkeys(base_pick + baseline_names))[:8]
        sens_pool = {k: r for k, r in active_rotations.items() if r.name in sens_names}

        sens_df = sensitivity_analysis(
            sens_pool, df, weights_norm, vary, steps=11, slot_cache=slot_cache,
        )

        fig_sens = px.line(
            sens_df, x="weight_value", y="total_score", color="rotation",
            labels={
                "weight_value": f"{WEIGHT_LABELS[vary]} weight",
                "total_score": "Total Score",
                "rotation": "Rotation",
            },
            title=f"Sensitivity (Selected / Top {len(sens_pool)}): Rankings vs {WEIGHT_LABELS[vary]} weight",
            template="plotly_white",
        )
        fig_sens.update_layout(height=400)
        st.plotly_chart(fig_sens, use_container_width=True)

        # Confidence note across full active ranking
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
