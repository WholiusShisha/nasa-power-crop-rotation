"""End-to-end smoke test: fetch POWER data, compute indicators, score rotations."""
import time
from power_api import fetch_power_data, DEMO_LOCATIONS
from crops import ROTATIONS
from indicators import (growing_season_length, heat_stress, dry_spell_analysis,
                        monthly_water_balance, mann_kendall_trend, apply_scenario)
from scoring import compare_rotations, score_rotation, sensitivity_analysis, DEFAULT_WEIGHTS

lat, lon = DEMO_LOCATIONS["Mekong Delta, Vietnam (Cần Thơ)"]
t = time.time()
df = fetch_power_data(lat, lon, 1990, 2023)
print(f"Fetched {df.shape} in {time.time()-t:.1f}s; NaNs per col:\n{df.isna().sum()}")
print(df.describe().T[["mean", "min", "max"]].round(2))

print("\nHeat stress days (median):", heat_stress(df, 35)["heat_stress_days"].median())
print("Max dry spell (median):", dry_spell_analysis(df)["max_dry_spell_days"].median())
annual_rain = df.groupby(df.index.year)["PRECTOTCORR"].sum()
print("Annual rain trend:", mann_kendall_trend(annual_rain)["interpretation"])

print("\n=== Ranking (default weights) ===")
print(compare_rotations(ROTATIONS, df).to_string())

print("\n=== Ranking (+2C, -15% rain) ===")
print(compare_rotations(ROTATIONS, apply_scenario(df, 2.0, 0.85)).to_string())

r = score_rotation(ROTATIONS["rice_rice"], df)
print("\nClimate-fit detail (baseline):")
for k, v in r["sub_scores"]["climate_fit"][1].items():
    print(" ", k, v)

s = sensitivity_analysis(ROTATIONS, df, DEFAULT_WEIGHTS, "water_saving", steps=3)
print("\nSensitivity sample:\n", s.to_string())
