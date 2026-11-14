import time, cProfile, pstats
from power_api import fetch_power_data
import scoring, crops
df = fetch_power_data(10.03, 105.78, 1990, 2023)
t = time.time()
r = scoring.compare_rotations(df, scoring.DEFAULT_WEIGHTS) if hasattr(scoring, "compare_rotations") else None
print("compare_rotations s:", round(time.time() - t, 1), flush=True)
