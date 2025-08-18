import json
import io
import pandas as pd
import streamlit as st
from orchestrator.workflow import run as run_workflow

st.set_page_config(page_title="GreenHouseAI Manager", page_icon="🌱", layout="wide")
st.title("🌱 GreenHouseAI Manager (MVP)")

with st.sidebar:
    st.header("Inputs")
    location = st.text_input("Location (city/country)", value="Colombo, Sri Lanka", key="location")
    area = st.number_input("Greenhouse area (m²)", min_value=10, max_value=10000, value=120, step=10, key="area")
    season = st.text_input("Season (free text)", value="Oct–Dec", key="season")
    goal = st.selectbox("Goal", ["balanced", "maximize_yield", "minimize_cost"], index=0, key="goal")
    organic = st.toggle("Organic preference", value=True, key="organic")

    if st.button("Generate Plan", type="primary"):
        with st.spinner("Thinking..."):
            results = run_workflow({
                "location": location,
                "area": area,
                "season": season,
                "goal": goal,
                "organic": organic,
            })
        st.session_state["results"] = results

results = st.session_state.get("results")

if not results:
    st.info("Fill inputs and click **Generate Plan** to produce a plan.")
    st.stop()

# ---- Tabs ----
tab1, tab2, tab3 = st.tabs(["Crop Plan", "Operations", "Market & Profit"])

with tab1:
    cp = results["crop_plan"]
    st.subheader("Recommended Crops & Area Split")
    df = pd.DataFrame([{"Crop": c["name"], "Area (m²)": c["area_m2"], "Cycle (days)": c["cycle_days"]} for c in cp["crops"]])
    st.dataframe(df, use_container_width=True)
    st.caption(f"Rationale: {cp.get('rationale', '')}")

with tab2:
    op = results["ops_plan"]
    st.subheader("Resource Cadence & Expected Yield (~10 weeks)")
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
    st.metric("Water Cost (USD)", f"{costs['water_usd']:.2f}")
    st.metric("Nutrient Cost (USD)", f"{costs['nutrients_usd']:.2f}")
    st.metric("Labor (USD)", f"{costs['labor_usd']:.2f}")
    st.metric("Misc (USD)", f"{costs['misc_usd']:.2f}")
    st.caption(op.get("notes", ""))

with tab3:
    mk = results["market_plan"]
    st.subheader("Profitability")
    col1, col2, col3 = st.columns(3)
    col1.metric("Revenue (USD)", f"{mk['revenue_usd']:.2f}")
    col2.metric("COGS (USD)", f"{mk['cogs_usd']:.2f}")
    col3.metric("Margin (%)", f"{mk['margin_pct']:.2f}")

    st.markdown("**Pricing Assumptions**")
    df3 = pd.DataFrame([{"Crop": p["crop"], "Price (USD/kg)": p["unit_price_usd_per_kg"]} for p in mk["pricing_assumptions"]])
    st.dataframe(df3, use_container_width=True)

    st.markdown("**Go-To-Market Ideas**")
    for idea in mk["go_to_market"]:
        st.write(f"- {idea}")

st.divider()
colA, colB = st.columns(2)

with colA:
    st.subheader("Download JSON")
    json_bytes = json.dumps(results, indent=2).encode("utf-8")
    st.download_button("⬇️ Download full plan (JSON)", data=json_bytes, file_name="greenhouse_plan.json", mime="application/json")

with colB:
    st.subheader("Download CSVs")
    # crops
    crops_csv = pd.DataFrame(results["crop_plan"]["crops"]).to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Crop Plan (CSV)", data=crops_csv, file_name="crop_plan.csv", mime="text/csv")
    # ops
    ops_csv = pd.DataFrame(results["ops_plan"]["crops"]).to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Ops Plan (CSV)", data=ops_csv, file_name="ops_plan.csv", mime="text/csv")
