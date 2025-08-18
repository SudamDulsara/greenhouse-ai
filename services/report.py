# services/report.py
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def _per_crop_profitability(plan: dict):
    mk = plan.get("market_plan", {})
    op = plan.get("ops_plan", {})
    price_map = {p["crop"].strip().lower(): float(p["unit_price_usd_per_kg"]) for p in mk.get("pricing_assumptions", [])}
    crops = op.get("crops", [])
    total_cogs = float(mk.get("cogs_usd", 0.0))
    total_yield = sum(float(c.get("expected_yield_kg", 0.0)) for c in crops) or 1.0

    rows = []
    for c in crops:
        name = c["name"]
        y = float(c.get("expected_yield_kg", 0.0))
        price = float(price_map.get(name.strip().lower(), 2.0))
        revenue = price * y
        cogs_alloc = total_cogs * (y / total_yield)
        profit = revenue - cogs_alloc
        margin_pct = (profit / revenue * 100.0) if revenue > 0 else 0.0
        rows.append({
            "name": name,
            "yield": round(y, 2),
            "price": round(price, 2),
            "revenue": round(revenue, 2),
            "cogs_alloc": round(cogs_alloc, 2),
            "profit": round(profit, 2),
            "margin_pct": round(margin_pct, 2),
        })
    return rows

def build_pdf(plan: dict) -> bytes:
    """
    Commercial one-pager:
      - Weather summary
      - Crop plan overview
      - Ops cadence & costs
      - Per-crop profitability
      - Overall revenue / margin + GTM ideas
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    x, y = 40, height - 40

    def writeln(text, step=14, bold=False):
        nonlocal y
        if bold:
            c.setFont("Helvetica-Bold", 11)
        else:
            c.setFont("Helvetica", 10)
        c.drawString(x, y, text[:120])
        y -= step
        if y < 60:
            c.showPage()
            y = height - 40

    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, y, "GreenHouseAI – Strategy Summary")
    y -= 22

    cp = plan.get("crop_plan", {})
    op = plan.get("ops_plan", {})
    mk = plan.get("market_plan", {})
    wx = plan.get("weather", {})

    # Weather
    writeln("Weather (next ~14 days)", bold=True)
    writeln(f"Avg Temp: {wx.get('avg_temp_c', 'n/a')}°C | Avg Precip: {wx.get('avg_precip_mm', 'n/a')} mm")
    y -= 6

    # Crop plan
    writeln("Crop Plan", bold=True)
    for citem in cp.get("crops", []):
        writeln(f"- {citem['name']}: area {citem['area_m2']} m², cycle {citem['cycle_days']} days")
    if cp.get("rationale"):
        writeln(f"Rationale: {cp.get('rationale','')}")
    y -= 6

    # Operations
    writeln("Operations (~10 weeks)", bold=True)
    for oc in op.get("crops", []):
        writeln(f"- {oc['name']}: water {oc['watering_l_per_day']} L/day, fert {oc['fertilizer_g_per_week']} g/week, expected {oc['expected_yield_kg']} kg")
    costs = op.get("costs", {})
    writeln(f"Costs: water ${costs.get('water_usd',0):.2f}, nutrients ${costs.get('nutrients_usd',0):.2f}, labor ${costs.get('labor_usd',0):.2f}, misc ${costs.get('misc_usd',0):.2f}")
    y -= 6

    # Per-crop profitability
    writeln("Per-Crop Profitability", bold=True)
    for row in _per_crop_profitability(plan):
        writeln(f"- {row['name']}: revenue ${row['revenue']:.2f}, COGS ${row['cogs_alloc']:.2f}, profit ${row['profit']:.2f} (margin {row['margin_pct']:.1f}%)")

    y -= 6
    # Market (overall)
    writeln("Market & Profit (Overall)", bold=True)
    writeln(f"Revenue: ${mk.get('revenue_usd',0):.2f} | COGS: ${mk.get('cogs_usd',0):.2f} | Margin: {mk.get('margin_pct',0):.2f}%")
    if mk.get("go_to_market"):
        writeln("Go-To-Market Ideas:", bold=True)
        for idea in mk["go_to_market"][:3]:
            writeln(f"- {idea}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()
