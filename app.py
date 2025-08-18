import json
from copy import deepcopy
import pandas as pd
import streamlit as st
from orchestrator.workflow import run as run_workflow
from storage.db import init_db, save_scenario, list_scenarios, load_scenario, delete_scenario
from services.weather import get_weather_summary
from services.report import build_pdf
from services.forex import get_rate, SUPPORTED as FX_SUPPORTED

st.set_page_config(page_title="GreenHouseAI Manager", page_icon="🌱", layout="wide")
st.title("🌱 GreenHouseAI Manager (MVP+)")

init_db()

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Inputs")
    location = st.text_input("Location (city/country)", value="Colombo, Sri Lanka", key="location")
    area = st.number_input("Greenhouse area (m²)", min_value=10, max_value=10000, value=120, step=10, key="area")
    season = st.text_input("Season (free text)", value="Oct–Dec", key="season")
    goal = st.selectbox("Goal", ["balanced", "maximize_yield", "minimize_cost"], index=0, key="goal")
    organic = st.toggle("Organic preference", value=True, key="organic")

    st.divider()
    st.subheader("Integrations (optional)")
    use_weather = st.checkbox("Use weather data (Open-Meteo)", value=True)
    use_custom_prices = st.checkbox("Use custom prices (upload CSV)", value=False)
    custom_prices_df = None
    if use_custom_prices:
        custom_prices_file = st.file_uploader("Upload prices.csv with columns: crop, price_usd_per_kg", type=["csv"])
        if custom_prices_file:
            try:
                custom_prices_df = pd.read_csv(custom_prices_file)
                st.success(f"Loaded custom prices with {len(custom_prices_df)} rows.")
            except Exception as e:
                st.error(f"Failed to parse CSV: {e}")
                custom_prices_df = None

    st.divider()
    st.subheader("What-if & Currency")
    area_pct = st.slider("Area adjustment (%)", min_value=50, max_value=150, value=100, step=5,
                         help="Scales yields and variable costs; keeps labor/misc constant.")
    price_pct = st.slider("Price adjustment (%)", min_value=-30, max_value=30, value=0, step=5,
                          help="Applies to all crop prices.")
    target_ccy = st.selectbox("Display currency", FX_SUPPORTED, index=FX_SUPPORTED.index("USD"))

    generate_clicked = st.button("Generate Plan", type="primary", use_container_width=True)

    st.divider()
    st.subheader("Save / Load Scenarios")
    scen_name = st.text_input("Scenario name", value="")
    save_btn = st.button("💾 Save Current Scenario", disabled=("results" not in st.session_state or not scen_name), use_container_width=True)

    scenarios = list_scenarios()
    if scenarios:
        options = {f"[{s.id}] {s.name} — {s.created_at:%Y-%m-%d %H:%M}": s.id for s in scenarios}
        pick = st.selectbox("Saved scenarios", list(options.keys()))
        load_btn = st.button("📂 Load Selected", use_container_width=True)
        delete_btn = st.button("🗑️ Delete Selected", use_container_width=True)
    else:
        st.caption("No saved scenarios yet.")

# ---------- Generate ----------
if generate_clicked:
    with st.spinner("Thinking..."):
        wx = get_weather_summary(location) if use_weather else None
        results = run_workflow(
            {
                "location": location,
                "area": area,
                "season": season,
                "goal": goal,
                "organic": organic,
            },
            weather=wx,
            pricing_df=custom_prices_df,
        )
    st.session_state["inputs"] = {"location": location, "area": area, "season": season, "goal": goal, "organic": organic}
    st.session_state["results"] = results

# ---------- Save / Load / Delete ----------
if "results" in st.session_state and save_btn and scen_name:
    sid = save_scenario(scen_name, st.session_state.get("inputs", {}), st.session_state["results"])
    st.success(f"Saved scenario #{sid} ✅")

if scenarios and 'pick' in locals():
    chosen_id = options.get(pick)
    if chosen_id and load_btn:
        st.session_state["results"] = load_scenario(chosen_id)
        st.success(f"Loaded scenario #{chosen_id} ✅")
    if chosen_id and delete_btn:
        delete_scenario(chosen_id)
        st.warning(f"Deleted scenario #{chosen_id} 🗑️")
        st.rerun()

results = st.session_state.get("results")
if not results:
    st.info("Fill inputs → enable integrations → **Generate Plan**.")
    st.stop()

# ---------- Helpers ----------
def compute_per_crop_profitability(results_dict: dict) -> pd.DataFrame:
    mk = results_dict["market_plan"]
    op = results_dict["ops_plan"]
    price_map = {p["crop"].strip().lower(): float(p["unit_price_usd_per_kg"]) for p in mk["pricing_assumptions"]}
    crops = op["crops"]
    total_cogs = float(mk["cogs_usd"])
    total_yield = sum(float(c["expected_yield_kg"]) for c in crops) or 1.0
    rows = []
    for c in crops:
        name = c["name"]
        y = float(c["expected_yield_kg"])
        price = float(price_map.get(name.strip().lower(), 2.0))
        revenue = price * y
        cogs_alloc = total_cogs * (y / total_yield)
        profit = revenue - cogs_alloc
        margin_pct = (profit / revenue * 100.0) if revenue > 0 else 0.0
        rows.append({
            "Crop": name,
            "Expected Yield (kg)": round(y, 2),
            "Price (USD/kg)": round(price, 2),
            "Revenue (USD)": round(revenue, 2),
            "Allocated COGS (USD)": round(cogs_alloc, 2),
            "Profit (USD)": round(profit, 2),
            "Margin (%)": round(margin_pct, 2),
        })
    return pd.DataFrame(rows)

def apply_what_if(base: dict, area_factor: float, price_factor: float) -> dict:
    """Create an adjusted plan WITHOUT extra LLM calls."""
    plan = deepcopy(base)
    # Scale ops crops: yields & variable cadences
    for c in plan["ops_plan"]["crops"]:
        c["expected_yield_kg"] = round(float(c["expected_yield_kg"]) * area_factor, 2)
        c["watering_l_per_day"] = round(float(c["watering_l_per_day"]) * area_factor, 2)
        c["fertilizer_g_per_week"] = round(float(c["fertilizer_g_per_week"]) * area_factor, 2)
    # Scale variable costs; keep labor & misc constant
    costs = plan["ops_plan"]["costs"]
    costs["water_usd"] = round(float(costs["water_usd"]) * area_factor, 2)
    costs["nutrients_usd"] = round(float(costs["nutrients_usd"]) * area_factor, 2)
    # Recompute revenue (apply price factor to USD/kg)
    mk = plan["market_plan"]
    for p in mk["pricing_assumptions"]:
        p["unit_price_usd_per_kg"] = round(float(p["unit_price_usd_per_kg"]) * (1.0 + price_factor), 4)
    price_map = {p["crop"].strip().lower(): float(p["unit_price_usd_per_kg"]) for p in mk["pricing_assumptions"]}
    revenue = 0.0
    for c in plan["ops_plan"]["crops"]:
        revenue += price_map.get(c["name"].strip().lower(), 0.0) * float(c["expected_yield_kg"])
    mk["revenue_usd"] = round(revenue, 2)
    mk["cogs_usd"] = round(sum(plan["ops_plan"]["costs"].values()), 2)
    mk["margin_pct"] = round(((revenue - mk["cogs_usd"]) / revenue * 100.0) if revenue > 0 else 0.0, 2)
    return plan

@st.cache_data(ttl=3600)
def fx_rate_cached(target: str) -> float:
    try:
        return get_rate("USD", target)
    except Exception:
        return 1.0

def as_ccy(amount_usd: float, rate: float) -> float:
    return round(float(amount_usd) * rate, 2)

# ---------- Base Summary ----------
mk = results["market_plan"]
cp = results["crop_plan"]
op = results["ops_plan"]
wx = results.get("weather", {})

chosen_crops = ", ".join([c["name"] for c in cp["crops"]])

colA, colB, colC, colD = st.columns(4)
colA.metric("Revenue (USD)", f"{mk['revenue_usd']:.2f}")
colB.metric("COGS (USD)", f"{mk['cogs_usd']:.2f}")
colC.metric("Margin (%)", f"{mk['margin_pct']:.2f}")
colD.metric("Avg Temp (°C)", f"{wx.get('avg_temp_c','—')}")
st.caption(f"Selected crops: {chosen_crops}")

# ---------- Tabs ----------
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Crop Plan", "Operations", "Market & Profit", "Charts", "What-if & Currency"])

with tab1:
    with st.expander("Recommended Crops & Area Split", expanded=True):
        df = pd.DataFrame([{"Crop": c["name"], "Area (m²)": c["area_m2"], "Cycle (days)": c["cycle_days"]} for c in cp["crops"]])
        st.dataframe(df, use_container_width=True)
        st.caption(f"Rationale: {cp.get('rationale', '')}")

with tab2:
    with st.expander("Resource Cadence & Expected Yield (~10 weeks)", expanded=True):
        df2 = pd.DataFrame([
            {
                "Crop": c["name"],
                "Water (L/day)": c["watering_l_per_day"],
                "Fertilizer (g/week)": c["fertilizer_g_per_week"],
                "Expected Yield (kg)": c["expected_yield_kg"],
            } for c in op["crops"]
        ])
        st.dataframe(df2, use_container_width=True)

        costs = op["costs"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Water Cost", f"${costs['water_usd']:.2f}")
        c2.metric("Nutrient Cost", f"${costs['nutrients_usd']:.2f}")
        c3.metric("Labor", f"${costs['labor_usd']:.2f}")
        c4.metric("Misc", f"${costs['misc_usd']:.2f}")
        st.caption(op.get("notes", ""))

with tab3:
    with st.expander("Profitability & Go-To-Market", expanded=True):
        per_crop = compute_per_crop_profitability(results)
        st.dataframe(per_crop, use_container_width=True)

        st.markdown("**Pricing Assumptions (USD/kg)**")
        df3 = pd.DataFrame([{"Crop": p["crop"], "Price (USD/kg)": p["unit_price_usd_per_kg"]} for p in mk["pricing_assumptions"]])
        st.dataframe(df3, use_container_width=True)

        st.markdown("**Go-To-Market Ideas**")
        for idea in mk["go_to_market"]:
            st.write(f"- {idea}")

with tab4:
    # Charts (base)
    per_crop = compute_per_crop_profitability(results)
    st.subheader("Revenue vs Allocated COGS (per crop) — Base")
    try:
        rv_cost = per_crop[["Crop", "Revenue (USD)", "Allocated COGS (USD)"]].set_index("Crop")
        st.bar_chart(rv_cost)
    except Exception:
        st.info("Chart data not available.")

    st.subheader("COGS Breakdown — Base")
    try:
        costs = op["costs"]
        pie_df = pd.DataFrame({
            "Component": ["Water", "Nutrients", "Labor", "Misc"],
            "USD": [costs["water_usd"], costs["nutrients_usd"], costs["labor_usd"], costs["misc_usd"]],
        }).set_index("Component")
        st.bar_chart(pie_df)
    except Exception:
        st.info("COGS data not available.")

with tab5:
    st.markdown("### What-if Scenario (no extra API/LLM calls)")
    area_factor = area_pct / 100.0
    price_factor = price_pct / 100.0
    adj = apply_what_if(results, area_factor, price_factor)

    rate = fx_rate_cached(target_ccy)

    # Summary (converted)
    mk2 = adj["market_plan"]
    col1, col2, col3 = st.columns(3)
    col1.metric(f"Revenue ({target_ccy})", f"{as_ccy(mk2['revenue_usd'], rate):.2f}")
    col2.metric(f"COGS ({target_ccy})", f"{as_ccy(mk2['cogs_usd'], rate):.2f}")
    col3.metric("Margin (%)", f"{mk2['margin_pct']:.2f}")

    st.caption(f"Applied: area ×{area_factor:.2f}, prices ×{1+price_factor:.2f}, FX USD→{target_ccy} @ {rate:.4f}")

    # Per-crop table (converted)
    per_crop2 = compute_per_crop_profitability(adj)
    # Convert monetary columns
    for col in ["Revenue (USD)", "Allocated COGS (USD)", "Profit (USD)"]:
        per_crop2[col.replace("USD", target_ccy)] = (per_crop2[col] * rate).round(2)
        del per_crop2[col]
    # Rename price column for clarity
    per_crop2.rename(columns={"Price (USD/kg)": f"Price ({target_ccy}/kg) (after adj, FX)"},
                     inplace=True)
    # Convert price using FX and price_factor already applied inside adj
    price_fx = []
    price_map_adj = {p["crop"].strip().lower(): float(p["unit_price_usd_per_kg"]) for p in mk2["pricing_assumptions"]}
    for _, row in per_crop2.iterrows():
        usd_per_kg = price_map_adj.get(row["Crop"].strip().lower(), 0.0)
        price_fx.append(round(usd_per_kg * rate, 4))
    per_crop2[f"Price ({target_ccy}/kg) (after adj, FX)"] = price_fx

    st.dataframe(per_crop2, use_container_width=True)

    # Charts (adjusted)
    st.subheader(f"Revenue vs Allocated COGS per crop — Adjusted ({target_ccy})")
    try:
        rv_cost2 = per_crop2[["Crop", f"Revenue ({target_ccy})", f"Allocated COGS ({target_ccy})"]].set_index("Crop")
        st.bar_chart(rv_cost2)
    except Exception:
        st.info("Adjusted chart data not available.")

# ---------- Downloads ----------
st.divider()
colX, colY, colZ = st.columns(3)

with colX:
    st.subheader("Download JSON")
    json_bytes = json.dumps(results, indent=2).encode("utf-8")
    st.download_button("⬇️ Full plan (JSON)", data=json_bytes, file_name="greenhouse_plan.json", mime="application/json")

with colY:
    st.subheader("Download CSVs")
    crops_csv = pd.DataFrame(results["crop_plan"]["crops"]).to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Crop Plan (CSV)", data=crops_csv, file_name="crop_plan.csv", mime="text/csv")
    ops_csv = pd.DataFrame(results["ops_plan"]["crops"]).to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Ops Plan (CSV)", data=ops_csv, file_name="ops_plan.csv", mime="text/csv")

with colZ:
    st.subheader("Export PDF")
    pdf_bytes = build_pdf(results)
    st.download_button("📄 Strategy Report (PDF)", data=pdf_bytes, file_name="greenhouse_strategy.pdf", mime="application/pdf")

# ---------- Diagnostics ----------
st.divider()
st.caption("Diagnostics")
cp_meta = results.get("crop_plan", {}).get("_meta", {})
advisor_elapsed = cp_meta.get("advisor_elapsed_s")
if advisor_elapsed is not None:
    st.caption(f"CropAdvisor latency: {advisor_elapsed}s (approx)")
if results.get("weather", {}).get("source"):
    st.caption(f"Weather source: {results['weather']['source']}")