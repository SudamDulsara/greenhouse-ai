# services/report.py
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def build_pdf(plan: dict) -> bytes:
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

    c.setFont("Helvetica-Bold", 14)
    c.drawString(x, y, "GreenHouseAI – Strategy Summary")
    y -= 24

    cp = plan.get("crop_plan", {})
    op = plan.get("ops_plan", {})
    mk = plan.get("market_plan", {})
    wx = plan.get("weather", {})

    writeln("Weather (next ~14 days)", bold=True)
    writeln(f"Avg Temp: {wx.get('avg_temp_c', 'n/a')}°C | Avg Precip: {wx.get('avg_precip_mm', 'n/a')} mm")
    y -= 6

    writeln("Crop Plan", bold=True)
    for citem in cp.get("crops", []):
        writeln(f"- {citem['name']}: area {citem['area_m2']} m², cycle {citem['cycle_days']} days")
    writeln(f"Rationale: {cp.get('rationale','')}")
    y -= 6

    writeln("Operations (~10 weeks)", bold=True)
    for oc in op.get("crops", []):
        writeln(f"- {oc['name']}: water {oc['watering_l_per_day']} L/day, fert {oc['fertilizer_g_per_week']} g/week, expected {oc['expected_yield_kg']} kg")
    costs = op.get("costs", {})
    writeln(f"Costs: water ${costs.get('water_usd',0):.2f}, nutrients ${costs.get('nutrients_usd',0):.2f}, labor ${costs.get('labor_usd',0):.2f}, misc ${costs.get('misc_usd',0):.2f}")
    y -= 6

    writeln("Market & Profit", bold=True)
    writeln(f"Revenue: ${mk.get('revenue_usd',0):.2f} | COGS: ${mk.get('cogs_usd',0):.2f} | Margin: {mk.get('margin_pct',0):.2f}%")
    for idea in mk.get("go_to_market", [])[:3]:
        writeln(f"- {idea}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()
