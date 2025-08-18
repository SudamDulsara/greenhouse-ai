# agents/market_analyst.py
from pydantic import BaseModel
from typing import List
import pandas as pd
from services.llm import chat_json_with_usage
from config import settings

class PricingAssumption(BaseModel):
    crop: str
    unit_price_usd_per_kg: float

class MarketPlan(BaseModel):
    revenue_usd: float
    cogs_usd: float
    margin_pct: float
    pricing_assumptions: List[PricingAssumption]
    go_to_market: List[str]

SYSTEM_PROMPT = """You are MarketAnalyst. Given the list of crops, expected yields, and a target market (retail),
propose 2–3 short go-to-market tactics focused on small to medium greenhouse businesses.
Return STRICT JSON with keys: go_to_market (list of strings).
"""

def _load_prices() -> pd.DataFrame:
    df = pd.read_csv("data/prices.csv")
    df.columns = [c.strip().lower() for c in df.columns]
    return df

def analyze_market(ops_plan, pricing_source: str = "csv", pricing_df: pd.DataFrame | None = None) -> MarketPlan:
    if pricing_df is not None:
        df = pricing_df.copy()
        df.columns = [c.strip().lower() for c in df.columns]
    else:
        df = _load_prices()

    # Expect columns: crop, price_usd_per_kg
    price_map = {}
    for _, row in df.iterrows():
        if "crop" in row and "price_usd_per_kg" in row:
            price_map[str(row["crop"]).strip().lower()] = float(row["price_usd_per_kg"])

    pricing_assumptions: List[PricingAssumption] = []
    revenue = 0.0
    for c in ops_plan.crops:
        unit_price = price_map.get(c.name.strip().lower(), 2.0)
        pricing_assumptions.append(PricingAssumption(crop=c.name, unit_price_usd_per_kg=unit_price))
        revenue += unit_price * c.expected_yield_kg

    cogs = sum(ops_plan.costs.values())
    margin_pct = 0.0
    if revenue > 0:
        margin_pct = round((revenue - cogs) / revenue * 100.0, 2)

    items = []
    try:
        user_prompt = f"""
Crops and expected yields:
{[(c.name, c.expected_yield_kg) for c in ops_plan.crops]}

Constraints:
- Audience: retail and small HORECA (cafes, restaurants).
- Keep suggestions crisp and actionable.
- 2–3 ideas max.
Return JSON with key go_to_market: ["idea1", "idea2", ...]
"""
        ideas, usage, elapsed = chat_json_with_usage(
            model=settings.model_small,
            system=SYSTEM_PROMPT,
            user=user_prompt,
        )
        items = [str(x) for x in ideas.get("go_to_market", [])][:3]
    except Exception:
        items = [
            "Bundle basil with tomatoes for caprese kits; sell to cafes.",
            "Offer weekly CSA-style subscription boxes.",
            "Target farm-to-table restaurants with consistent supply contracts.",
        ]

    return MarketPlan(
        revenue_usd=round(revenue, 2),
        cogs_usd=round(cogs, 2),
        margin_pct=margin_pct,
        pricing_assumptions=pricing_assumptions,
        go_to_market=items,
    )
