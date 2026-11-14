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
    source_note: str = ""             # FAO / IRRI / WorldVeg reference note


CROP_DB: Dict[str, CropTraits] = {
    "rice": CropTraits(
        name="Rice (wet-season)",
        family="Poaceae",
        season_days=(90, 150),
        temp_min=12, temp_opt_low=22, temp_opt_high=32, temp_max=35,
        water_need_mm=(900, 1300),
        drought_tolerance="low",
        nitrogen_fixing=False,
        rooting_depth="shallow",
        market_value="medium",
        typical_season="Jun–Nov",
        description="Staple paddy rice; field water need includes puddling/percolation (ETc 500–700 mm); flowering sterility rises above 35 °C.",
        color="#2E86C1",
        source_note="IRRI (35 °C anthesis sterility); FAO Water Dev.",
    ),
    "rice_dry": CropTraits(
        name="Rice (dry-season)",
        family="Poaceae",
        season_days=(90, 115),
        temp_min=12, temp_opt_low=22, temp_opt_high=32, temp_max=35,
        water_need_mm=(800, 1200),
        drought_tolerance="low",
        nitrogen_fixing=False,
        rooting_depth="shallow",
        market_value="medium",
        typical_season="Dec–Apr",
        description="Short-duration irrigated dry-season rice; higher evaporative demand and heat exposure at flowering.",
        color="#5DADE2",
        source_note="IRRI / FAO I&D 56 (higher dry-season ET0)",
    ),
    "maize": CropTraits(
        name="Maize (Corn)",
        family="Poaceae",
        season_days=(80, 120),
        temp_min=10, temp_opt_low=18, temp_opt_high=32, temp_max=38,
        water_need_mm=(500, 800),
        drought_tolerance="medium",
        nitrogen_fixing=False,
        rooting_depth="deep",
        market_value="medium",
        typical_season="Feb–Jun or Aug–Dec",
        description="Deep-rooted cereal; tolerates drier conditions than rice, but pollen viability drops above 38 °C.",
        color="#F39C12",
        source_note="FAO I&D 24/56 (500–800 mm); EcoCrop",
    ),
    "soybean": CropTraits(
        name="Soybean",
        family="Fabaceae",
        season_days=(75, 115),
        temp_min=10, temp_opt_low=20, temp_opt_high=30, temp_max=37,
        water_need_mm=(450, 700),
        drought_tolerance="medium",
        nitrogen_fixing=True,
        rooting_depth="medium",
        market_value="high",
        typical_season="Feb–May or Aug–Nov",
        description="Fixes atmospheric nitrogen and breaks cereal pest cycles; sensitive to waterlogging.",
        color="#27AE60",
        source_note="FAO I&D 24/56 (450–700 mm); EcoCrop",
    ),
    "mung_bean": CropTraits(
        name="Mung Bean",
        family="Fabaceae",
        season_days=(60, 90),
        temp_min=15, temp_opt_low=25, temp_opt_high=32, temp_max=38,
        water_need_mm=(250, 400),
        drought_tolerance="high",
        nitrogen_fixing=True,
        rooting_depth="medium",
        market_value="high",
        typical_season="Mar–May (short gap crop)",
        description="Chilling-sensitive quick legume with a 0.5–1.0 m taproot; fits short gaps on residual moisture.",
        color="#1ABC9C",
        source_note="WorldVeg / FAO EcoCrop (base ~15 °C, taproot)",
    ),
    "sweet_potato": CropTraits(
        name="Sweet Potato",
        family="Convolvulaceae",
        season_days=(90, 150),
        temp_min=15, temp_opt_low=21, temp_opt_high=29, temp_max=36,
        water_need_mm=(400, 675),
        drought_tolerance="high",
        nitrogen_fixing=False,
        rooting_depth="medium",
        market_value="medium",
        typical_season="Year-round where warm",
        description="Dense canopy protects soil from erosion; storage root bulking slows above 30 °C.",
        color="#8E44AD",
        source_note="FAO I&D 24 (400–675 mm); EcoCrop (<30 °C bulking)",
    ),
    "peanut": CropTraits(
        name="Peanut (Groundnut)",
        family="Fabaceae",
        season_days=(90, 130),
        temp_min=13, temp_opt_low=24, temp_opt_high=32, temp_max=37,
        water_need_mm=(500, 700),
        drought_tolerance="high",
        nitrogen_fixing=True,
        rooting_depth="medium",
        market_value="high",
        typical_season="Feb–Jun",
        description="Drought-hardy nitrogen fixer; needs loose, well-drained soil for pegging; heat >37 °C cuts pod set.",
        color="#D4AC0D",
        source_note="FAO I&D 24/56 (500–700 mm); ICRISAT",
    ),
    "vegetables": CropTraits(
        name="Leafy Brassicas (Greens)",
        family="Brassicaceae",
        season_days=(30, 60),
        temp_min=10, temp_opt_low=18, temp_opt_high=28, temp_max=35,
        water_need_mm=(250, 400),
        drought_tolerance="low",
        nitrogen_fixing=False,
        rooting_depth="shallow",
        market_value="high",
        typical_season="Oct–Mar (cooler months)",
        description="Fast-maturing leafy brassicas (e.g., mustard greens, cabbage family); high value per ha, needs steady moisture.",
        color="#E74C3C",
        source_note="FAO CROPWAT / WorldVeg (Brassicaceae)",
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
        description="Traditional double-rice rotation. High irrigation burden and zero family diversity.",
        is_baseline=True,
        slots=[
            RotationSlot("rice_dry", start_month=12, end_month=3, label="Dry-season rice"),
            RotationSlot("rice", start_month=6, end_month=10, label="Wet-season rice"),
        ],
    ),
    "rice_maize": Rotation(
        name="Rice–Maize",
        description="Replace dry-season rice with maize to save water and deepen rooting depth.",
        slots=[
            RotationSlot("maize", start_month=12, end_month=3, label="Dry-season maize"),
            RotationSlot("rice", start_month=6, end_month=10, label="Wet-season rice"),
        ],
    ),
    "rice_peanut": Rotation(
        name="Rice–Peanut",
        description="Upland dry-season legume breaks rice pest cycles, fixes nitrogen, and tolerates dry spells.",
        slots=[
            RotationSlot("rice", start_month=6, end_month=10, label="Wet-season rice"),
            RotationSlot("peanut", start_month=1, end_month=4, label="Peanut"),
        ],
    ),
    "rice_sweet_potato": Rotation(
        name="Rice–Sweet Potato",
        description="Drought-hardy tuber crop follows wet rice for dense soil cover and water conservation.",
        slots=[
            RotationSlot("rice", start_month=6, end_month=10, label="Wet-season rice"),
            RotationSlot("sweet_potato", start_month=12, end_month=4, label="Sweet potato"),
        ],
    ),
    "rice_soy_veg": Rotation(
        name="Rice–Soybean–Leafy Brassicas",
        description="Triple crop: wet rice, then soybean (N-fix), then cool-season leafy brassicas.",
        slots=[
            RotationSlot("rice", start_month=6, end_month=9, label="Wet-season rice"),
            RotationSlot("soybean", start_month=10, end_month=12, label="Soybean"),
            RotationSlot("vegetables", start_month=1, end_month=3, label="Leafy brassicas"),
        ],
    ),
    "rice_mung_maize": Rotation(
        name="Rice–Mung Bean–Maize",
        description="Maximize soil cover and N-fixation with a short legume gap crop before maize.",
        slots=[
            RotationSlot("rice", start_month=6, end_month=10, label="Wet-season rice"),
            RotationSlot("mung_bean", start_month=11, end_month=1, label="Mung bean"),
            RotationSlot("maize", start_month=2, end_month=5, label="Dry-season maize"),
        ],
    ),
    "rice_soy_maize": Rotation(
        name="Rice–Soybean–Maize",
        description="Three-crop intensive system pairing wet rice with high-value N-fixing soybean and maize.",
        slots=[
            RotationSlot("rice", start_month=6, end_month=9, label="Wet-season rice"),
            RotationSlot("soybean", start_month=10, end_month=12, label="Soybean"),
            RotationSlot("maize", start_month=1, end_month=4, label="Dry-season maize"),
        ],
    ),
    "rice_mung_peanut": Rotation(
        name="Rice–Mung Bean–Peanut",
        description="Low-water double-legume upland sequence after wet rice; strong pest break and N input.",
        slots=[
            RotationSlot("rice", start_month=6, end_month=9, label="Wet-season rice"),
            RotationSlot("mung_bean", start_month=10, end_month=12, label="Mung bean"),
            RotationSlot("peanut", start_month=1, end_month=4, label="Peanut"),
        ],
    ),
}


_SHORT_NAMES = {
    "rice": "Wet Rice",
    "rice_dry": "Dry Rice",
    "maize": "Maize",
    "soybean": "Soybean",
    "mung_bean": "Mung Bean",
    "sweet_potato": "Sweet Potato",
    "peanut": "Peanut",
    "vegetables": "Brassicas",
}


def generate_rotation_combinations(
    wet_crops: List[str],
    gap_crops: List[str],
    dry_crops: List[str],
    include_2crop: bool = True,
    include_3crop: bool = True,
) -> Dict[str, Rotation]:
    """
    Generate valid 2-crop (Wet Jun–Oct + Dry Dec–Mar / Jan–Apr) and
    3-crop (Wet Jun–Sep + Cool/Gap Oct–Dec + Dry Jan–Apr) combinations.

    Skips adjacent identical crop keys (while allowing `rice` + `rice_dry`).
    """
    combos: Dict[str, Rotation] = {}

    if include_2crop:
        for w in wet_crops:
            for d in dry_crops:
                if w == d:
                    continue
                d_start, d_end = (12, 3) if d == "rice_dry" else (1, 4)
                key = f"gen_2_{w}_{d}"
                name = f"{_SHORT_NAMES.get(w, w)} → {_SHORT_NAMES.get(d, d)} [2-crop]"
                combos[key] = Rotation(
                    name=name,
                    description="Auto-generated 2-crop combination (Wet Jun–Oct, Dry Dec–Mar/Jan–Apr).",
                    slots=[
                        RotationSlot(w, 6, 10, label=f"Wet: {_SHORT_NAMES.get(w, w)}"),
                        RotationSlot(d, d_start, d_end, label=f"Dry: {_SHORT_NAMES.get(d, d)}"),
                    ],
                )

    if include_3crop:
        for w in wet_crops:
            for g in gap_crops:
                if w == g:
                    continue
                for d in dry_crops:
                    if g == d or d == w:
                        continue
                    key = f"gen_3_{w}_{g}_{d}"
                    name = (
                        f"{_SHORT_NAMES.get(w, w)} → {_SHORT_NAMES.get(g, g)} "
                        f"→ {_SHORT_NAMES.get(d, d)} [3-crop]"
                    )
                    combos[key] = Rotation(
                        name=name,
                        description="Auto-generated 3-crop combination (Jun–Sep, Oct–Dec, Jan–Apr).",
                        slots=[
                            RotationSlot(w, 6, 9, label=f"Wet: {_SHORT_NAMES.get(w, w)}"),
                            RotationSlot(g, 10, 12, label=f"Gap: {_SHORT_NAMES.get(g, g)}"),
                            RotationSlot(d, 1, 4, label=f"Dry: {_SHORT_NAMES.get(d, d)}"),
                        ],
                    )

    return combos


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
            "Source": c.source_note,
        })
    return pd.DataFrame(rows)
