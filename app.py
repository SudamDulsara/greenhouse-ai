import streamlit as st

st.set_page_config(page_title="GreenHouseAI Manager", page_icon="🌱", layout="wide")

st.title("🌱 GreenHouseAI Manager (MVP)")
st.caption("Phase 0 scaffold — next step: wire agents and orchestrator.")

with st.sidebar:
    st.header("Inputs")
    st.text_input("Location (city/country)", value="Colombo, Sri Lanka", key="location")
    st.number_input("Greenhouse area (m²)", min_value=10, max_value=10000, value=120, step=10, key="area")
    st.text_input("Season (free text)", value="Oct–Dec", key="season")
    goal = st.selectbox("Goal", ["balanced", "maximize_yield", "minimize_cost"], index=0, key="goal")
    organic = st.toggle("Organic preference", value=True, key="organic")

    run = st.button("Generate Plan (disabled until Phase 1)", type="primary", disabled=True)

st.info("✅ Phase 0 complete. Click 'Run' will be enabled in Phase 1 when agents are implemented.")
