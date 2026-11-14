"""
Crop trait table and rotation definitions.

Focused on Southeast Asian / Mekong Delta context with 5–8 candidate crops.
All thresholds sourced from FAO Crop Water Information and IRRI guidelines.
Values are simplified for a decision-support demo — NOT authoritative agronomic data.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ---------------------------------------------------------------------------
# Crop trait data
# ---------------------------------------------------------------------------

@dataclass
class CropTraits:
    """Simplified agronomic profile for one crop."""
    name: str
    family: str                       # botanical family (for pest-cycle break)
    season_days: tuple                # (min, max) days to maturity
    temp_min: float                   # absolute minimum growing temp (°C)
    temp_opt_low: float               # lower optimal temp (°C)
    temp_opt_high: float              # upper optimal temp (°C)
    temp_max: float                   # absolute maximum growing temp (°C)
    water_need_mm: tuple              # (min, max) total water need over season (mm)
    drought_tolerance: str            # low / medium / high
    nitrogen_fixing: bool
    rooting_depth: str                # shallow / medium / deep
    market_value: str                 # low / medium / high  (qualitative)
    typical_season: str               # which calendar months it's typically planted
    description: str                  # farmer-friendly note
    color: str                        # for charts


CROP_DB: Dict[str, CropTraits] = {
    "rice": CropTraits(
        name="Rice (wet-season)",
        family="Poaceae",
        season_days=(90, 150),
        temp_min=10, temp_opt_low=22, temp_opt_high=30, temp_max=40,
        water_need_mm=(900, 1400),
        drought_tolerance="low",
        nitrogen_fixing=False,
        rooting_depth="shallow",
        market_value="medium",
        typical_season="Jun–Nov",
        description="Staple paddy rice; needs standing water for most of the season.",
        color="#2E86C1",
    ),
    "rice_dry": CropTraits(
        name="Rice (dry-season)",
        family="Poaceae",
        season_days=(90, 120),
        temp_min=10, temp_opt_low=22, temp_opt_high=30, temp_max=40,
        water_need_mm=(700, 1100),
        drought_tolerance="low",
        nitrogen_fixing=False,
        rooting_depth="shallow",
        market_value="medium",
        typical_season="Dec–Apr",
        description="Short-duration irrigated rice in the dry season.",
        color="#5DADE2",
    ),
    "maize": CropTraits(
        name="Maize (Corn)",
        family="Poaceae",
        season_days=(80, 120),
        temp_min=8, temp_opt_low=18, temp_opt_high=33, temp_max=42,
        water_need_mm=(400, 700),
        drought_tolerance="medium",
        nitrogen_fixing=False,
        rooting_depth="deep",
        market_value="medium",
        typical_season="Feb–Jun or Aug–Dec",
        description="Versatile cereal; tolerates drier conditions than rice.",
        color="#F39C12",
    ),
    "soybean": CropTraits(
        name="Soybean",
        family="Fabaceae",
        season_days=(75, 120),
        temp_min=10, temp_opt_low=20, temp_opt_high=30, temp_max=38,
        water_need_mm=(350, 600),
        drought_tolerance="medium",
        nitrogen_fixing=True,
        rooting_depth="medium",
        market_value="high",
        typical_season="Feb–May or Aug–Nov",
        description="Fixes nitrogen, improves soil for the next crop.",
        color="#27AE60",
    ),
    "mung_bean": CropTraits(
        name="Mung Bean",
        family="Fabaceae",
        season_days=(60, 90),
        temp_min=10, temp_opt_low=25, temp_opt_high=35, temp_max=40,
        water_need_mm=(250, 400),
        drought_tolerance="high",
        nitrogen_fixing=True,
        rooting_depth="shallow",
        market_value="high",
        typical_season="Mar–May (short gap crop)",
        description="Quick-growing legume; great for short windows between rice.",
        color="#1ABC9C",
    ),
    "sweet_potato": CropTraits(
        name="Sweet Potato",
        family="Convolvulaceae",
        season_days=(90, 150),
        temp_min=15, temp_opt_low=24, temp_opt_high=30, temp_max=38,
        water_need_mm=(400, 700),
        drought_tolerance="high",
        nitrogen_fixing=False,
        rooting_depth="medium",
        market_value="medium",
        typical_season="Year-round where warm",
        description="Tolerates poor soils; dense cover reduces erosion.",
        color="#8E44AD",
    ),
    "peanut": CropTraits(
        name="Peanut (Groundnut)",
        family="Fabaceae",
        season_days=(90, 130),
        temp_min=12, temp_opt_low=25, temp_opt_high=30, temp_max=40,
        water_need_mm=(400, 600),
        drought_tolerance="medium",
        nitrogen_fixing=True,
        rooting_depth="medium",
        market_value="high",
        typical_season="Feb–Jun",
        description="Nitrogen-fixer with good market value; needs well-drained soil.",
        color="#D4AC0D",
    ),
    "vegetables": CropTraits(
        name="Vegetables (leafy)",
        family="Various",
        season_days=(30, 60),
        temp_min=10, temp_opt_low=18, temp_opt_high=28, temp_max=35,
        water_need_mm=(200, 400),
        drought_tolerance="low",
        nitrogen_fixing=False,
        rooting_depth="shallow",
        market_value="high",
        typical_season="Oct–Mar (cooler months)",
        description="High income per hectare; labor-intensive, perishable.",
        color="#E74C3C",
    ),
}


# ---------------------------------------------------------------------------
# Rotation definitions
# ---------------------------------------------------------------------------

@dataclass
class RotationSlot:
    """One slot in a rotation calendar."""
    crop_key: str                   # key into CROP_DB
    start_month: int                # 1-12
    end_month: int                  # 1-12  (can wrap around)
    label: Optional[str] = None     # display override

    @property
    def crop(self) -> CropTraits:
        return CROP_DB[self.crop_key]

    @property
    def months(self) -> List[int]:
        """List of months this slot occupies (handles wrap-around)."""
        if self.start_month <= self.end_month:
            return list(range(self.start_month, self.end_month + 1))
        else:
            return list(range(self.start_month, 13)) + list(range(1, self.end_month + 1))


@dataclass
class Rotation:
    """A full annual rotation strategy."""
    name: str
    description: str
    slots: List[RotationSlot]
    is_baseline: bool = False

    @property
    def bare_months(self) -> List[int]:
        """Months with no crop cover (fallow / bare field)."""
        covered = set()
        for slot in self.slots:
            covered.update(slot.months)
        return sorted(set(range(1, 13)) - covered)

    @property
    def unique_families(self) -> int:
        """Number of distinct crop families (pest-cycle diversity)."""
        return len({slot.crop.family for slot in self.slots})

    @property
    def has_legume(self) -> bool:
        return any(slot.crop.nitrogen_fixing for slot in self.slots)


# Pre-defined rotations for the Mekong Delta demo
ROTATIONS: Dict[str, Rotation] = {
    "rice_rice": Rotation(
        name="Rice–Rice (Baseline)",
        description="Traditional double-rice rotation. High water use, familiar to farmers.",
        is_baseline=True,
        slots=[
            RotationSlot("rice_dry", start_month=12, end_month=3, label="Dry-season rice"),
            RotationSlot("rice", start_month=6, end_month=10, label="Wet-season rice"),
        ],
    ),
    "rice_maize": Rotation(
        name="Rice–Maize",
        description="Replace dry-season rice with maize to save water and diversify income.",
        slots=[
            RotationSlot("maize", start_month=12, end_month=3, label="Dry-season maize"),
            RotationSlot("rice", start_month=6, end_month=10, label="Wet-season rice"),
        ],
    ),
    "rice_soy_veg": Rotation(
        name="Rice–Soybean–Vegetables",
        description="Triple crop: wet rice, then soybean (N-fix), then quick vegetables.",
        slots=[
            RotationSlot("rice", start_month=6, end_month=9, label="Wet-season rice"),
            RotationSlot("soybean", start_month=10, end_month=12, label="Soybean"),
            RotationSlot("vegetables", start_month=1, end_month=3, label="Vegetables"),
        ],
    ),
    "rice_mung_maize": Rotation(
        name="Rice–Mung Bean–Maize",
        description="Maximize soil cover and N-fixation with a legume gap crop.",
        slots=[
            RotationSlot("rice", start_month=6, end_month=10, label="Wet-season rice"),
            RotationSlot("mung_bean", start_month=11, end_month=1, label="Mung bean"),
            RotationSlot("maize", start_month=2, end_month=5, label="Dry-season maize"),
        ],
    ),
}


def get_crop_table_df():
    """Return a pandas DataFrame of the crop trait table for display."""
    import pandas as pd
    rows = []
    for key, c in CROP_DB.items():
        rows.append({
            "Crop": c.name,
            "Family": c.family,
            "Season (days)": f"{c.season_days[0]}–{c.season_days[1]}",
            "Temp range (°C)": f"{c.temp_min}–{c.temp_max}",
            "Optimal (°C)": f"{c.temp_opt_low}–{c.temp_opt_high}",
            "Water (mm)": f"{c.water_need_mm[0]}–{c.water_need_mm[1]}",
            "Drought tol.": c.drought_tolerance,
            "N-fixing": "✅" if c.nitrogen_fixing else "❌",
            "Root depth": c.rooting_depth,
            "Market value": c.market_value,
        })
    return pd.DataFrame(rows)
