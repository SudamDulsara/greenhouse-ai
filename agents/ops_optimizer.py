# agents/ops_optimizer.py
from pydantic import BaseModel
from typing import List, Dict
import pandas as pd

class OpsCrop(BaseModel):
    name: str
    watering_l_per_day: float
    fertilizer_g_per_week: float
    expected_yield_kg: float

class OpsPlan(BaseModel):
    crops: List[OpsCrop]
    costs: Dict[str, float]  # water_usd, nutrients_usd, labor_usd, misc_usd
    notes: str = ""

# Simple per-m2 heuristics (can tune later)
WATER_L_PER_M2_DAY_DEFAULTS = {
    "tomato": 3.0,
    "basil": 1.2,
    "cucumber": 2.8,
    "lettuce": 1.5,
}
FERT_G_PER_M2_WEEK_DEFAULTS = {
    "tomato": 45.0,
    "basil": 12.0,
    "cucumber": 35.0,
    "lettuce": 15.0,
}

WATER_PRICE_PER_L = 0.0010  # USD
NUTRIENT_PRICE_PER_G = 0.01 # USD
LABOR_COST_BASE = 120.0     # USD per cycle, simple flat assumption
MISC_COST = 25.0            # USD

def _load_catalog() -> pd.DataFrame:
    df = pd.read_csv("data/crops.csv")
    df.columns = [c.strip().lower() for c in df.columns]
    return df

def optimize_operations(crop_plan, user_prefs: dict, weather: dict | None = None) -> OpsPlan:
    """
    Compute watering, fertilizer, expected yield using crop catalog yields and area.
    Costs computed from simple unit prices and ~10-week horizon.
    If weather provided, adjust water by temperature deviation from 22°C baseline.
    """
    catalog = _load_catalog()
    cat_map = {row["crop"].strip().lower(): row for _, row in catalog.iterrows()}

    goal = user_prefs.get("goal", "balanced")
    organic = bool(user_prefs.get("organic", True))

    temp = (weather or {}).get("avg_temp_c", 22.0)
    temp_factor = 1.0 + max(min((temp - 22.0) / 5.0 * 0.10, 0.30), -0.30)

    crops_out: List[OpsCrop] = []
    total_water_cost = 0.0
    total_nutrient_cost = 0.0

    horizon_days = 70
    horizon_weeks = 10

    for item in crop_plan.crops:
        key = item.name.strip().lower()
        area = float(item.area_m2)
        yield_per_m2 = float(cat_map.get(key, {}).get("yield_kg_per_m2", 3.0))

        cycles_in_horizon = max(horizon_days / max(1, int(item.cycle_days)), 0.5)
        expected_yield = round(yield_per_m2 * area * cycles_in_horizon, 2)

        water_per_m2_day = WATER_L_PER_M2_DAY_DEFAULTS.get(key, 2.0)
        fert_per_m2_week = FERT_G_PER_M2_WEEK_DEFAULTS.get(key, 15.0)

        if goal == "minimize_cost":
            water_per_m2_day *= 0.9
            fert_per_m2_week *= 0.85
        elif goal == "maximize_yield":
            water_per_m2_day *= 1.1
            fert_per_m2_week *= 1.15

        if organic:
            fert_per_m2_week *= 0.9

        water_per_m2_day *= temp_factor

        water_l_day = round(water_per_m2_day * area, 2)
        fert_g_week = round(fert_per_m2_week * area, 2)

        crops_out.append(
            OpsCrop(
                name=item.name,
                watering_l_per_day=water_l_day,
                fertilizer_g_per_week=fert_g_week,
                expected_yield_kg=expected_yield,
            )
        )

        total_water_cost += water_l_day * horizon_days * WATER_PRICE_PER_L
        total_nutrient_cost += fert_g_week * horizon_weeks * NUTRIENT_PRICE_PER_G

    costs = {
        "water_usd": round(total_water_cost, 2),
        "nutrients_usd": round(total_nutrient_cost, 2),
        "labor_usd": round(LABOR_COST_BASE, 2),
        "misc_usd": round(MISC_COST, 2),
    }

    notes = "Parameters tuned for a ~10-week horizon. Weather-adjusted watering applied."
    return OpsPlan(crops=crops_out, costs=costs, notes=notes)
