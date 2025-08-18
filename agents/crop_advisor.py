from pydantic import BaseModel, Field
from typing import List

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

def generate_crop_plan(user_inputs: dict) -> CropPlan:
    raise NotImplementedError("Phase 1 will implement CropAdvisor.")