import json
import pandas as pd
import streamlit as st
from orchestrator.workflow import run as run_workflow
from storage.db import init_db, save_scenario, list_scenarios, load_scenario, delete_scenario
from services.weather import get_weather_summary
from services.report import build_pdf

st.set_page_config(page_title="GreenHouseAI Manager", page_icon="🌱", layout="wide")
st.title("🌱 GreenHouseAI Manager (MVP+)")

init_db()

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

mk = results["market_plan"]
cp = results["crop_plan"]
op = results["ops_plan"]
wx = results.get("weather", {})

colA, colB, colC, colD = st.columns(4)
colA.metric("Revenue (USD)", f"{mk['revenue_usd']:.2f}")
colB.metric("COGS (USD)", f"{mk['cogs_usd']:.2f}")
colC.metric("Margin (%)", f"{mk['margin_pct']:.2f}")
colD.metric("Avg Temp (°C)", f"{wx.get('avg_temp_c','—')}")

tab1, tab2, tab3 = st.tabs(["Crop Plan", "Operations", "Market & Profit"])

with tab1:
    st.subheader("Recommended Crops & Area Split")
    df = pd.DataFrame([{"Crop": c["name"], "Area (m²)": c["area_m2"], "Cycle (days)": c["cycle_days"]} for c in cp["crops"]])
    st.dataframe(df, use_container_width=True)
    st.caption(f"Rationale: {cp.get('rationale', '')}")

with tab2:
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
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Water Cost", f"${costs['water_usd']:.2f}")
    c2.metric("Nutrient Cost", f"${costs['nutrients_usd']:.2f}")
    c3.metric("Labor", f"${costs['labor_usd']:.2f}")
    c4.metric("Misc", f"${costs['misc_usd']:.2f}")
    st.caption(op.get("notes", ""))

with tab3:
    st.subheader("Profitability & Go-To-Market")
    col1, col2 = st.columns([1,1])

    try:
        chart_df = pd.DataFrame({"Type": ["Revenue", "COGS"], "USD": [mk["revenue_usd"], mk["cogs_usd"]]})
        col1.bar_chart(chart_df.set_index("Type"))
    except Exception:
        pass

    st.markdown("**Pricing Assumptions**")
    df3 = pd.DataFrame([{"Crop": p["crop"], "Price (USD/kg)": p["unit_price_usd_per_kg"]} for p in mk["pricing_assumptions"]])
    st.dataframe(df3, use_container_width=True)

    st.markdown("**Go-To-Market Ideas**")
    for idea in mk["go_to_market"]:
        st.write(f"- {idea}")

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

st.divider()
st.caption("Diagnostics")
cp_meta = results.get("crop_plan", {}).get("_meta", {})
advisor_elapsed = cp_meta.get("advisor_elapsed_s")
if advisor_elapsed is not None:
    st.caption(f"CropAdvisor latency: {advisor_elapsed}s (approx)")
if results.get("weather", {}).get("source"):
    st.caption(f"Weather source: {results['weather']['source']}")
