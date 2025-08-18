# orchestrator/workflow.py
from typing import Optional
import pandas as pd
from agents.crop_advisor import generate_crop_plan
from agents.ops_optimizer import optimize_operations
from agents.market_analyst import analyze_market

def run(user_inputs: dict, weather: Optional[dict] = None, pricing_df: Optional[pd.DataFrame] = None) -> dict:
    """
    1) CropAdvisor -> CropPlan (uses weather if provided)
    2) OpsOptimizer -> OpsPlan (uses weather if provided)
    3) MarketAnalyst -> MarketPlan (uses pricing_df if provided)
    """
    crop_plan = generate_crop_plan(user_inputs, weather=weather)
    ops_plan = optimize_operations(crop_plan, {"goal": user_inputs["goal"], "organic": user_inputs["organic"]}, weather=weather)
    market_plan = analyze_market(ops_plan, pricing_source="csv", pricing_df=pricing_df)

    return {
        "crop_plan": crop_plan.model_dump(),
        "ops_plan": ops_plan.model_dump(),
        "market_plan": market_plan.model_dump(),
        "weather": weather or {},
    }
