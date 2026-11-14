"""
NASA POWER API client.

Fetches daily weather/solar data from the POWER Data Access Viewer (DAV) v2 API.
Docs: https://power.larc.nasa.gov/docs/services/api/

All data is returned as a pandas DataFrame with a DatetimeIndex.
Includes caching to avoid re-fetching during development.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import List, Optional

import pandas as pd
import numpy as np
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

POWER_API_BASE = "https://power.larc.nasa.gov/api/temporal/daily/point"

# Parameters we need for crop-rotation analysis
DEFAULT_PARAMETERS = [
    "T2M",              # Temperature at 2m (°C) — daily mean
    "T2M_MAX",          # Daily max temperature at 2m
    "T2M_MIN",          # Daily min temperature at 2m
    "PRECTOTCORR",      # Corrected total precipitation (mm/day)
    "EVLAND",           # Evaporation from land (mm/day, MERRA-2)
    "GWETROOT",         # Root-zone soil wetness (0–1 fraction)
    "GWETTOP",          # Surface soil wetness (0–1 fraction)
    "RH2M",             # Relative humidity at 2m (%)
    "ALLSKY_SFC_SW_DWN", # All-sky surface shortwave downward irradiance (MJ/m²/day)
]

CACHE_DIR = Path(__file__).parent / ".cache"


# ---------------------------------------------------------------------------
# API fetch
# ---------------------------------------------------------------------------

def _cache_key(lat: float, lon: float, start: str, end: str, params: List[str]) -> str:
    """Deterministic cache filename."""
    raw = f"{lat}_{lon}_{start}_{end}_{'_'.join(sorted(params))}"
    h = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"power_{h}.parquet"


def fetch_power_data(
    lat: float,
    lon: float,
    start_year: int = 1984,
    end_year: int = 2023,
    parameters: Optional[List[str]] = None,
    community: str = "AG",            # AG = Agroclimatology
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Fetch daily data from NASA POWER for a single point.

    Parameters
    ----------
    lat, lon : float
        Latitude and longitude of the location.
    start_year, end_year : int
        Year range (inclusive). POWER provides 1981–near present.
    parameters : list of str, optional
        POWER parameter names. Defaults to DEFAULT_PARAMETERS.
    community : str
        POWER community string (AG, RE, SB).
    use_cache : bool
        If True, cache results locally as Parquet.

    Returns
    -------
    pd.DataFrame
        Daily data with DatetimeIndex and one column per parameter.
    """
    if parameters is None:
        parameters = DEFAULT_PARAMETERS

    start_str = f"{start_year}0101"
    end_str = f"{end_year}1231"
    cache_file = CACHE_DIR / _cache_key(lat, lon, start_str, end_str, parameters)

    # Try cache first
    if use_cache and cache_file.exists():
        return pd.read_parquet(cache_file)

    # Build API request
    params_csv = ",".join(parameters)
    url = (
        f"{POWER_API_BASE}"
        f"?parameters={params_csv}"
        f"&community={community}"
        f"&longitude={lon}"
        f"&latitude={lat}"
        f"&start={start_str}"
        f"&end={end_str}"
        f"&format=JSON"
    )

    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    # Parse the nested parameter dict into a DataFrame
    param_data = data["properties"]["parameter"]
    records = {}
    for pname, daily_dict in param_data.items():
        records[pname] = daily_dict

    df = pd.DataFrame(records)
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df.index.name = "date"

    # POWER uses -999 for missing values
    df.replace(-999.0, np.nan, inplace=True)
    df.replace(-999, np.nan, inplace=True)

    # Cache
    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache_file)

    return df


def get_location_info(lat: float, lon: float) -> dict:
    """Return basic metadata about the location from POWER."""
    return {
        "latitude": lat,
        "longitude": lon,
        "resolution": "~0.5° × 0.625° (~50 km)",
        "source": "NASA POWER (MERRA-2 reanalysis)",
        "note": (
            "This is modeled reanalysis data, NOT ground-station measurements. "
            "Actual conditions at your farm may differ due to local topography, "
            "irrigation, and land cover."
        ),
    }


# ---------------------------------------------------------------------------
# Convenience: demo locations
# ---------------------------------------------------------------------------

DEMO_LOCATIONS = {
    "Mekong Delta, Vietnam (Cần Thơ)": (10.03, 105.78),
    "Central Highlands, Vietnam (Buôn Ma Thuột)": (12.67, 108.05),
    "Central Java, Indonesia": (-7.57, 110.82),
    "Punjab, India (Ludhiana)": (30.90, 75.86),
    "Nile Delta, Egypt (Tanta)": (30.79, 31.00),
    "Mato Grosso, Brazil (Sinop)": (-11.86, -55.51),
    "Iowa, USA (Ames)": (42.03, -93.47),
}
