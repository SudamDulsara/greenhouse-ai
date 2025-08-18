from agents.crop_advisor import generate_crop_plan
from agents.ops_optimizer import optimize_operations
from agents.market_analyst import analyze_market

def run(user_inputs: dict) -> dict:
    """
    1) CropAdvisor -> CropPlan
    2) OpsOptimizer -> OpsPlan
    3) MarketAnalyst -> MarketPlan
    Returns dict friendly for UI.
    """
    crop_plan = generate_crop_plan(user_inputs)
    ops_plan = optimize_operations(crop_plan, {"goal": user_inputs["goal"], "organic": user_inputs["organic"]})
    market_plan = analyze_market(ops_plan, pricing_source="csv")

    return {
        "crop_plan": crop_plan.model_dump(),
        "ops_plan": ops_plan.model_dump(),
        "market_plan": market_plan.model_dump(),
    }
