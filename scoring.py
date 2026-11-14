"""
Rotation scoring engine.

Uses a weighted, rule-based model to rank rotations against farmer priorities.
Fully explainable: every score component traces back to an indicator + crop trait.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional

from crops import CROP_DB, Rotation, RotationSlot
from indicators import crop_climate_fit, indicator_percentile_range


# ---------------------------------------------------------------------------
# Default priority weights (farmer can adjust via sliders)
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS = {
    "climate_fit":   0.25,   # How well crops match local climate
    "water_saving":  0.20,   # Lower total water need is better
    "soil_health":   0.20,   # N-fixing, soil cover, root diversity
    "pest_break":    0.15,   # Different crop families break pest cycles
    "income":        0.20,   # Market value of the crops
}

WEIGHT_LABELS = {
    "climate_fit":  "🌡️ Climate Fit",
    "water_saving": "💧 Water Saving",
    "soil_health":  "🌱 Soil Health",
    "pest_break":   "🐛 Pest-Cycle Break",
    "income":       "💰 Income Potential",
}


# ---------------------------------------------------------------------------
# Sub-score functions
# ---------------------------------------------------------------------------

def score_climate_fit(
    rotation: Rotation,
    df: pd.DataFrame,
    slot_cache: Optional[Dict] = None,
) -> Tuple[float, Dict]:
    """
    Average climate-fit score across all slots in the rotation.
    """
    slot_scores = {}
    for slot in rotation.slots:
        label = slot.label or slot.crop.name
        cache_key = ("fit", slot.crop_key, slot.start_month, slot.end_month)
        if slot_cache is not None and cache_key in slot_cache:
            fit = slot_cache[cache_key]
        else:
            fit = crop_climate_fit(df, slot.crop, slot.start_month, slot.end_month)
            if slot_cache is not None:
                slot_cache[cache_key] = fit
        slot_scores[label] = fit
    avg = np.mean([s["overall"] for s in slot_scores.values()])
    return round(float(avg), 1), slot_scores


EFFECTIVE_RAIN_FRACTION = 0.8   # share of rainfall usable by the crop (FAO rule of thumb)
IRRIGATION_WORST_MM = 1500      # irrigation demand that scores 0


def _season_rain(df: pd.DataFrame, start_month: int, end_month: int) -> float:
    """Median (across years) total rainfall within a season window."""
    m = df.index.month
    mask = (m >= start_month) & (m <= end_month) if start_month <= end_month \
        else (m >= start_month) | (m <= end_month)
    s = df[mask]
    # Group seasons that wrap the new year into one "season year"
    season_year = s.index.year + ((s.index.month >= start_month) & (start_month > end_month)).astype(int)
    return float(s.groupby(season_year)["PRECTOTCORR"].sum().median())


def score_water_saving(
    rotation: Rotation,
    df: pd.DataFrame,
    slot_cache: Optional[Dict] = None,
) -> Tuple[float, Dict]:
    """
    Score based on estimated irrigation demand (lower = better):
        irrigation = max(0, crop water need − 0.8 × median seasonal rainfall)
    Uses POWER rainfall, so the score responds to location and scenario.
    """
    detail = {}
    total_irr = 0.0
    for slot in rotation.slots:
        need = float(np.mean(slot.crop.water_need_mm))
        rain_key = ("rain", slot.start_month, slot.end_month)
        if slot_cache is not None and rain_key in slot_cache:
            rain = slot_cache[rain_key]
        else:
            rain = _season_rain(df, slot.start_month, slot.end_month)
            if slot_cache is not None:
                slot_cache[rain_key] = rain
        irr = max(0.0, need - EFFECTIVE_RAIN_FRACTION * rain)
        total_irr += irr
        detail[slot.label or slot.crop.name] = (
            f"need {need:.0f} mm, rain {rain:.0f} mm → irrigate ~{irr:.0f} mm"
        )
    score = max(0, min(100, (1 - total_irr / IRRIGATION_WORST_MM) * 100))
    detail["total_irrigation_mm"] = f"{total_irr:.0f} mm"
    detail["total_irrigation_val"] = int(round(total_irr))
    return round(float(score), 1), detail


def score_soil_health(rotation: Rotation) -> Tuple[float, Dict]:
    """
    Composite soil-health score:
    - N-fixing bonus (0 or 30)
    - Bare-month penalty (fewer bare months = better)
    - Root diversity bonus
    """
    n_fix_bonus = 30 if rotation.has_legume else 0
    n_bare = len(rotation.bare_months)
    bare_penalty = n_bare * 5  # 5 points per bare month
    # Root depth diversity
    depths = {slot.crop.rooting_depth for slot in rotation.slots}
    root_bonus = len(depths) * 10  # up to 30

    score = max(0, min(100, 50 + n_fix_bonus - bare_penalty + root_bonus))
    detail = {
        "n_fixing": "Yes" if rotation.has_legume else "No",
        "bare_months": n_bare,
        "bare_month_list": rotation.bare_months,
        "root_depth_diversity": len(depths),
    }
    return round(score, 1), detail


def score_pest_break(rotation: Rotation) -> Tuple[float, Dict]:
    """
    More distinct crop families = better pest/disease cycle break.
    """
    families = {slot.crop.family for slot in rotation.slots}
    n_fam = len(families)
    n_slots = len(rotation.slots)
    # 1 family = 20, 2 = 60, 3+ = 90+
    score = min(100, 20 + (n_fam - 1) * 35)
    detail = {
        "unique_families": n_fam,
        "families": sorted(families),
        "slots": n_slots,
    }
    return round(score, 1), detail


def score_income(rotation: Rotation) -> Tuple[float, Dict]:
    """
    Qualitative market-value score based on crop market values.
    """
    value_map = {"low": 30, "medium": 60, "high": 90}
    slot_values = {
        (slot.label or slot.crop.name): value_map.get(slot.crop.market_value, 50)
        for slot in rotation.slots
    }
    avg = np.mean(list(slot_values.values()))
    return round(avg, 1), slot_values


# ---------------------------------------------------------------------------
# Full rotation scoring
# ---------------------------------------------------------------------------

def score_rotation(
    rotation: Rotation,
    df: pd.DataFrame,
    weights: Optional[Dict[str, float]] = None,
    slot_cache: Optional[Dict] = None,
) -> Dict:
    """
    Compute the full weighted score for a rotation.

    Returns
    -------
    dict with:
        - total_score : float (0–100)
        - sub_scores : dict of category → (score, detail)
        - weights_used : dict
        - evidence : list of str (human-readable explanations)
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    # Normalize weights
    w_sum = sum(weights.values())
    w = {k: v / w_sum for k, v in weights.items()} if w_sum > 0 else DEFAULT_WEIGHTS

    # Compute sub-scores
    climate_s, climate_d = score_climate_fit(rotation, df, slot_cache=slot_cache)
    water_s, water_d = score_water_saving(rotation, df, slot_cache=slot_cache)
    soil_s, soil_d = score_soil_health(rotation)
    pest_s, pest_d = score_pest_break(rotation)
    income_s, income_d = score_income(rotation)

    sub_scores = {
        "climate_fit":  (climate_s, climate_d),
        "water_saving": (water_s, water_d),
        "soil_health":  (soil_s, soil_d),
        "pest_break":   (pest_s, pest_d),
        "income":       (income_s, income_d),
    }

    total = sum(w[k] * sub_scores[k][0] for k in w)

    # Build evidence strings
    evidence = _build_evidence(rotation, sub_scores)

    return {
        "rotation_name": rotation.name,
        "total_score": round(float(total), 1),
        "sub_scores": sub_scores,
        "weights_used": w,
        "evidence": evidence,
    }


def _build_evidence(rotation: Rotation, sub_scores: Dict) -> List[str]:
    """Generate human-readable evidence strings for the scorecard."""
    ev = []

    # Climate fit
    cs = sub_scores["climate_fit"][0]
    if cs >= 75:
        ev.append(f"✅ Good climate match (score {cs}/100) — crops suit local temperatures and rainfall.")
    elif cs >= 50:
        ev.append(f"⚠️ Moderate climate match ({cs}/100) — some seasons are marginal; check heat or water stress.")
    else:
        ev.append(f"❌ Poor climate match ({cs}/100) — significant temperature or rainfall mismatch.")

    # Water
    ws = sub_scores["water_saving"][0]
    detail = sub_scores["water_saving"][1]
    ev.append(
        f"💧 Estimated irrigation needed beyond rainfall: {detail.get('total_irrigation_mm', '?')}/yr "
        f"— score {ws}/100. (Based on POWER seasonal rainfall; assumes 80% is usable.)"
    )
    # Flag rain-fed mismatch in any season
    for label, fit in sub_scores["climate_fit"][1].items():
        if fit.get("water_score", 100) < 40:
            ev.append(
                f"⚠️ {label}: seasonal rainfall (~{fit['detail']['median_rain_mm']:.0f} mm) is far below "
                f"crop need — only viable with reliable irrigation."
            )
        if fit.get("detail", {}).get("pct_too_hot", 0) > 5:
            ev.append(f"🔥 {label}: {fit['detail']['pct_too_hot']:.0f}% of days exceed the crop's heat limit.")

    # Soil health
    ss = sub_scores["soil_health"][0]
    sd = sub_scores["soil_health"][1]
    if rotation.has_legume:
        ev.append("🌱 Includes a nitrogen-fixing legume — improves soil fertility.")
    bare = sd.get("bare_months", 0)
    if bare > 0:
        ev.append(f"⚠️ {bare} bare month(s) with no crop cover (erosion risk in months {sd.get('bare_month_list', [])}).")
    else:
        ev.append("✅ Full year crop cover — minimal erosion risk.")

    # Pest break
    ps = sub_scores["pest_break"][0]
    pd_detail = sub_scores["pest_break"][1]
    fams = pd_detail.get("families", [])
    if len(fams) >= 3:
        ev.append(f"✅ Strong pest-cycle break: {len(fams)} different crop families ({', '.join(fams)}).")
    elif len(fams) == 2:
        ev.append(f"⚠️ Moderate pest-cycle break: 2 families ({', '.join(fams)}).")
    else:
        ev.append(f"❌ No family diversity — same pests and diseases may persist.")

    # Income
    inc = sub_scores["income"][0]
    if inc >= 75:
        ev.append(f"💰 High income potential (score {inc}/100).")
    else:
        ev.append(f"💰 Income potential: {inc}/100.")

    # Needs-review notes
    ev.append("📋 Needs local review: actual soil type, irrigation availability, market access, labor.")

    return ev


# ---------------------------------------------------------------------------
# Compare all rotations
# ---------------------------------------------------------------------------

def compare_rotations(
    rotations: Dict[str, Rotation],
    df: pd.DataFrame,
    weights: Optional[Dict[str, float]] = None,
    slot_cache: Optional[Dict] = None,
) -> pd.DataFrame:
    """
    Score and rank all rotations.

    Returns a DataFrame sorted by total_score descending.
    """
    if slot_cache is None:
        slot_cache = {}
    results = []
    for key, rot in rotations.items():
        result = score_rotation(rot, df, weights, slot_cache=slot_cache)
        irr_val = result["sub_scores"]["water_saving"][1].get("total_irrigation_val", 0)
        row = {
            "Rotation": result["rotation_name"],
            "Total Score": result["total_score"],
            "Baseline": "⭐" if rot.is_baseline else "",
            "Crops/yr": len(rot.slots),
            "Families": rot.unique_families,
            "N-Fix": "Yes" if rot.has_legume else "No",
            "Bare Months": len(rot.bare_months),
            "Est. Irrigation (mm)": irr_val,
        }
        for cat, (score, _) in result["sub_scores"].items():
            row[WEIGHT_LABELS.get(cat, cat)] = score
        results.append(row)

    if not results:
        cols = [
            "Rotation", "Total Score", "Baseline", "Crops/yr",
            "Families", "N-Fix", "Bare Months", "Est. Irrigation (mm)",
            *WEIGHT_LABELS.values(),
        ]
        return pd.DataFrame(columns=cols)

    ranking = pd.DataFrame(results).sort_values("Total Score", ascending=False).reset_index(drop=True)
    ranking.index = ranking.index + 1  # 1-based rank
    ranking.index.name = "Rank"
    return ranking


def sensitivity_analysis(
    rotations: Dict[str, Rotation],
    df: pd.DataFrame,
    base_weights: Dict[str, float],
    vary_key: str,
    steps: int = 11,
    slot_cache: Optional[Dict] = None,
) -> pd.DataFrame:
    """
    Show how rankings change as one weight goes from 0 to 1.

    Returns a DataFrame with columns: weight_value, rotation, total_score.
    """
    if slot_cache is None:
        slot_cache = {}
    # Sub-scores depend only on climate and crop traits, not weights; compute once per rotation.
    w_base = base_weights if sum(base_weights.values()) > 0 else DEFAULT_WEIGHTS
    precomputed = {}
    for rot in rotations.values():
        res = score_rotation(rot, df, w_base, slot_cache=slot_cache)
        precomputed[rot.name] = {k: score for k, (score, _) in res["sub_scores"].items()}

    rows = []
    others_sum = sum(v for k, v in base_weights.items() if k != vary_key)
    for i in range(steps):
        test_w = base_weights.copy()
        val = i / (steps - 1)
        test_w[vary_key] = val
        # Reduce others proportionally
        if others_sum > 0:
            for k in test_w:
                if k != vary_key:
                    test_w[k] = base_weights[k] / others_sum * (1 - val)

        w_sum = sum(test_w.values())
        w_norm = {k: v / w_sum for k, v in test_w.items()} if w_sum > 0 else DEFAULT_WEIGHTS

        for rot_name, sub_scores in precomputed.items():
            total = sum(w_norm[k] * sub_scores[k] for k in w_norm)
            rows.append({
                "weight_value": round(val, 2),
                "rotation": rot_name,
                "total_score": round(float(total), 1),
            })

    return pd.DataFrame(rows)
