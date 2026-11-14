"""
Climate indicator computation from daily POWER data.

Each function takes a daily DataFrame (from power_api.fetch_power_data)
and returns farmer-readable indicators with uncertainty ranges.
"""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, Tuple, Optional


# ---------------------------------------------------------------------------
# Per-year / per-month indicator computation
# ---------------------------------------------------------------------------

def growing_season_length(df: pd.DataFrame, temp_threshold: float = 10.0) -> pd.DataFrame:
    """
    Days per year where mean temperature exceeds a crop's base temperature.

    Returns DataFrame with columns: year, growing_days.
    """
    return (
        (df["T2M"] >= temp_threshold)
        .groupby(df.index.year.rename("year"))
        .sum()
        .reset_index(name="growing_days")
    )


def frost_risk(df: pd.DataFrame, threshold: float = 2.0) -> pd.DataFrame:
    """
    Days per year with T2M_MIN below a threshold (frost / cold damage risk).
    """
    return (
        (df["T2M_MIN"] <= threshold)
        .groupby(df.index.year.rename("year"))
        .sum()
        .reset_index(name="frost_days")
    )


def heat_stress(df: pd.DataFrame, threshold: float = 35.0) -> pd.DataFrame:
    """
    Days per year with T2M_MAX above a crop's heat-stress threshold.
    """
    return (
        (df["T2M_MAX"] >= threshold)
        .groupby(df.index.year.rename("year"))
        .sum()
        .reset_index(name="heat_stress_days")
    )


def monthly_water_balance(df: pd.DataFrame) -> pd.DataFrame:
    """
    Monthly rainfall minus evaporation (mm).

    Positive = surplus; negative = deficit.
    """
    monthly = df.groupby(
        [df.index.year.rename("year"), df.index.month.rename("month")]
    ).agg(
        rain_mm=("PRECTOTCORR", "sum"),
        evap_mm=("EVLAND", "sum"),
    ).reset_index()
    monthly["water_balance_mm"] = monthly["rain_mm"] - monthly["evap_mm"]
    return monthly


def _max_dry_run(is_dry: np.ndarray) -> int:
    """Longest consecutive True run in a 1D boolean array."""
    if len(is_dry) == 0 or not is_dry.any():
        return 0
    padded = np.concatenate(([False], is_dry, [False]))
    diffs = np.diff(padded.astype(np.int8))
    starts = np.flatnonzero(diffs == 1)
    ends = np.flatnonzero(diffs == -1)
    return int((ends - starts).max())


def dry_spell_analysis(df: pd.DataFrame, threshold_mm: float = 1.0) -> pd.DataFrame:
    """
    Longest consecutive dry-day run per year (rain < threshold).
    """
    dry_series = df["PRECTOTCORR"] < threshold_mm
    results = [
        {"year": year, "max_dry_spell_days": _max_dry_run(group.to_numpy())}
        for year, group in dry_series.groupby(df.index.year.rename("year"))
    ]
    return pd.DataFrame(results)


def soil_wetness_seasonal(df: pd.DataFrame) -> pd.DataFrame:
    """
    Monthly average root-zone soil wetness (GWETROOT) and anomaly vs. long-term mean.
    """
    # Monthly means
    monthly = df.groupby(
        [df.index.year.rename("year"), df.index.month.rename("month")]
    ).agg(
        gwetroot_mean=("GWETROOT", "mean"),
        gwettop_mean=("GWETTOP", "mean"),
    ).reset_index()

    # Long-term monthly mean for anomaly
    lt_mean = monthly.groupby("month")["gwetroot_mean"].transform("mean")
    monthly["gwetroot_anomaly"] = monthly["gwetroot_mean"] - lt_mean
    return monthly


def bare_field_erosion_risk(
    df: pd.DataFrame,
    covered_months: list,
) -> pd.DataFrame:
    """
    For months where no crop covers the field, compute rainfall intensity
    as an erosion risk proxy.

    Parameters
    ----------
    covered_months : list of int
        Months (1–12) when a crop is growing (soil protected).

    Returns
    -------
    DataFrame with bare-month rainfall and risk flag.
    """
    bare = set(range(1, 13)) - set(covered_months)
    monthly = df.groupby(
        [df.index.year.rename("year"), df.index.month.rename("month")]
    ).agg(
        rain_mm=("PRECTOTCORR", "sum"),
    ).reset_index()
    monthly["is_bare"] = monthly["month"].isin(bare)
    monthly["erosion_risk"] = monthly["is_bare"] & (monthly["rain_mm"] > 100)
    return monthly


# ---------------------------------------------------------------------------
# Trend analysis
# ---------------------------------------------------------------------------

def linear_trend(series: pd.Series) -> Dict:
    """
    Simple linear regression trend on a yearly series.

    Returns slope, p-value, and interpretation.
    """
    x = np.arange(len(series))
    y = series.values.astype(float)
    mask = ~np.isnan(y)
    if mask.sum() < 5:
        return {"slope": np.nan, "p_value": np.nan, "interpretation": "Insufficient data"}

    slope, intercept, r, p, se = stats.linregress(x[mask], y[mask])
    per_decade = slope * 10

    if p < 0.05:
        direction = "increasing" if slope > 0 else "decreasing"
        interp = f"Significant {direction} trend ({per_decade:+.2f} per decade, p={p:.3f})"
    else:
        interp = f"No significant trend (p={p:.2f})"

    return {
        "slope_per_year": float(slope),
        "intercept": float(intercept),
        "slope_per_decade": float(per_decade),
        "p_value": float(p),
        "r_squared": float(r**2),
        "interpretation": interp,
    }


def mann_kendall_trend(series: pd.Series) -> Dict:
    """
    Non-parametric Mann-Kendall trend test.
    Falls back gracefully if pymannkendall not available.
    """
    try:
        import pymannkendall as mk
        y = series.dropna().values.astype(float)
        if len(y) < 10:
            return {"interpretation": "Insufficient data for Mann-Kendall"}
        result = mk.original_test(y)
        return {
            "trend": str(result.trend),
            "p_value": float(result.p),
            "tau": float(result.Tau),
            "slope_sen": float(result.slope),
            "interpretation": (
                f"{result.trend.capitalize()} (τ={result.Tau:.3f}, "
                f"Sen's slope={result.slope:.4f}, p={result.p:.3f})"
            ),
        }
    except ImportError:
        return linear_trend(series)  # fallback


# ---------------------------------------------------------------------------
# Climate-fit score for a single crop in a given season
# ---------------------------------------------------------------------------

def crop_climate_fit(
    df: pd.DataFrame,
    crop_traits,
    start_month: int,
    end_month: int,
) -> Dict:
    """
    Score how well local climate matches a crop's requirements for a
    particular season window.

    Returns a dict with sub-scores (0–100 each) and an overall fit score.
    """
    # Extract the relevant months
    if start_month <= end_month:
        season_mask = (df.index.month >= start_month) & (df.index.month <= end_month)
    else:
        season_mask = (df.index.month >= start_month) | (df.index.month <= end_month)

    season_df = df[season_mask]
    if season_df.empty:
        return {"overall": 0, "detail": "No data for this season window"}

    # --- Temperature fit ---
    t_mean = season_df["T2M"].mean()
    in_optimal = (
        (season_df["T2M"] >= crop_traits.temp_opt_low) &
        (season_df["T2M"] <= crop_traits.temp_opt_high)
    ).mean() * 100

    too_hot = (season_df["T2M_MAX"] >= crop_traits.temp_max).mean() * 100
    too_cold = (season_df["T2M_MIN"] <= crop_traits.temp_min).mean() * 100
    temp_score = max(0, in_optimal - too_hot * 2 - too_cold * 2)

    # --- Water fit ---
    # Total rainfall in the season vs. crop water need
    # Seasons that wrap past December are grouped into one "season year"
    wraps = start_month > end_month
    season_year = season_df.index.year + (
        (season_df.index.month >= start_month) & wraps
    ).astype(int)
    yearly_rain = season_df.groupby(season_year)["PRECTOTCORR"].sum()
    median_rain = yearly_rain.median()
    water_need_mid = np.mean(crop_traits.water_need_mm)

    if water_need_mid > 0:
        water_ratio = median_rain / water_need_mid
        if water_ratio >= 0.8 and water_ratio <= 1.5:
            water_score = 90 + min(10, (1.0 - abs(water_ratio - 1.0)) * 10)
        elif water_ratio >= 0.5:
            water_score = 60 + (water_ratio - 0.5) / 0.3 * 30
        else:
            water_score = max(0, water_ratio / 0.5 * 60)
    else:
        water_score = 50

    # --- Dry spell risk ---
    # Compute max dry spell within season months per year
    dry_mask = season_df["PRECTOTCORR"] < 1.0
    dry_spells = [
        _max_dry_run(group.to_numpy())
        for _, group in dry_mask.groupby(season_year)
    ]
    avg_dry = float(np.mean(dry_spells)) if dry_spells else 0.0

    if crop_traits.drought_tolerance == "high":
        dry_penalty = max(0, (avg_dry - 20) * 1.5)
    elif crop_traits.drought_tolerance == "medium":
        dry_penalty = max(0, (avg_dry - 14) * 2.0)
    else:
        dry_penalty = max(0, (avg_dry - 7) * 3.0)
    dry_spell_score = max(0, 100 - dry_penalty)

    # --- Overall ---
    overall = (temp_score * 0.35 + water_score * 0.40 + dry_spell_score * 0.25)

    return {
        "overall": round(overall, 1),
        "temp_score": round(temp_score, 1),
        "water_score": round(water_score, 1),
        "dry_spell_score": round(dry_spell_score, 1),
        "detail": {
            "mean_temp": round(t_mean, 1),
            "pct_optimal_temp": round(in_optimal, 1),
            "pct_too_hot": round(too_hot, 1),
            "pct_too_cold": round(too_cold, 1),
            "median_rain_mm": round(float(median_rain), 0),
            "avg_max_dry_spell": round(avg_dry, 1),
        },
    }


# ---------------------------------------------------------------------------
# Percentile ranges for uncertainty display
# ---------------------------------------------------------------------------

def indicator_percentile_range(
    yearly_series: pd.Series,
    lo: int = 10,
    hi: int = 90,
) -> Dict:
    """Return the lo–hi percentile range plus median for a yearly indicator."""
    vals = yearly_series.dropna()
    if len(vals) < 3:
        return {"median": np.nan, f"p{lo}": np.nan, f"p{hi}": np.nan}
    return {
        "median": float(np.median(vals)),
        f"p{lo}": float(np.percentile(vals, lo)),
        f"p{hi}": float(np.percentile(vals, hi)),
    }


# ---------------------------------------------------------------------------
# Scenario perturbation (climate change slider)
# ---------------------------------------------------------------------------

def apply_scenario(
    df: pd.DataFrame,
    temp_delta: float = 0.0,
    rain_factor: float = 1.0,
) -> pd.DataFrame:
    """
    Apply a simple climate-change scenario to the historical data.

    Parameters
    ----------
    temp_delta : float
        Add this many °C to all temperature columns.
    rain_factor : float
        Multiply rainfall by this factor (e.g. 0.85 = 15% less rain).

    Returns
    -------
    Modified copy of df.
    """
    out = df.copy()
    for col in ["T2M", "T2M_MAX", "T2M_MIN"]:
        if col in out.columns:
            out[col] = out[col] + temp_delta
    if "PRECTOTCORR" in out.columns:
        out["PRECTOTCORR"] = out["PRECTOTCORR"] * rain_factor
    return out
