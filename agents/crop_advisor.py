from pydantic import BaseModel, Field, ValidationError
from typing import List
import pandas as pd
from services.llm import chat_json

class CropItem(BaseModel):
    name: str
    area_m2: float
    cycle_days: int

class CropPlan(BaseModel):
    location: str
    greenhouse_area_m2: float
    season: str
    crops: List[CropItem]
    rationale: str = Field(default="")

SYSTEM_PROMPT = """You are CropAdvisor, planning greenhouse crops for a software-only simulator.
Pick 2–4 crops from the provided list. Respect total area. Prefer combos with compatible cycles and commercial demand.
Output STRICT JSON with: location, greenhouse_area_m2, season, crops[{name, area_m2, cycle_days}], rationale.
Do not include keys not in the schema.
"""

def _load_crops_catalog() -> pd.DataFrame:
    df = pd.read_csv("data/crops.csv")
    # normalize column names
    df.columns = [c.strip().lower() for c in df.columns]
    return df

def generate_crop_plan(user_inputs: dict) -> CropPlan:
    """
    user_inputs: {location, area, season, goal, organic}
    LLM chooses crops and area split.
    """
    catalog = _load_crops_catalog()
    crops_list = ", ".join(sorted(catalog["crop"].unique().tolist()))
    area = float(user_inputs["area"])
    location = str(user_inputs["location"])
    season = str(user_inputs["season"])
    goal = str(user_inputs["goal"])
    organic = bool(user_inputs["organic"])

    user_prompt = f"""
        Available crops: {crops_list}
        Total greenhouse area: {area} m2
        Location: {location}
        Season: {season}
        User goal: {goal}
        Organic preference: {organic}

        Rules:
        - Choose only from the available crops list.
        - Total of all area_m2 must be <= {area}.
        - cycle_days should be roughly based on known cycle lengths; you may adapt slightly to align cycles.
        - Prefer 2–4 crops.
        - Keep rationale to 2–3 sentences.

        Return JSON ONLY with keys: location, greenhouse_area_m2, season, crops, rationale.
        """

    data = chat_json(
        model="gpt-4o-mini",
        system=SYSTEM_PROMPT,
        user=user_prompt,
    )

    data.setdefault("location", location)
    data.setdefault("greenhouse_area_m2", area)
    data.setdefault("season", season)

    valid_names = set(c.strip().lower() for c in catalog["crop"].tolist())
    filtered = []
    for c in data.get("crops", []):
        name = c.get("name", "").strip()
        if name.lower() in valid_names:
            filtered.append(c)
    data["crops"] = filtered

    tot = sum(c["area_m2"] for c in data.get("crops", []) if "area_m2" in c)
    if tot > 0 and tot > area:
        ratio = area / tot
        for c in data["crops"]:
            c["area_m2"] = round(c["area_m2"] * ratio, 2)

    try:
        return CropPlan(**data)
    except ValidationError as e:
        fallback = {
            "location": location,
            "greenhouse_area_m2": area,
            "season": season,
            "crops": [
                {"name": "Tomato", "area_m2": round(area * 0.7, 2), "cycle_days": 75},
                {"name": "Basil", "area_m2": round(area * 0.3, 2), "cycle_days": 30},
            ],
            "rationale": "Fallback plan due to validation error.",
        }
        return CropPlan(**fallback)
