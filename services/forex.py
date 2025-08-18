# services/forex.py
from typing import Dict
import requests

SUPPORTED = ["USD", "EUR", "GBP", "LKR", "AUD", "CAD", "JPY", "INR", "SGD"]

def get_rate(base: str = "USD", target: str = "USD") -> float:
    """
    Live FX via Frankfurter (ECB). No key required.
    Returns the rate to convert 1 base -> target.
    """
    base = (base or "USD").upper()
    target = (target or "USD").upper()
    if base == target:
        return 1.0
    r = requests.get("https://api.frankfurter.app/latest",
                     params={"from": base, "to": target}, timeout=10)
    r.raise_for_status()
    data = r.json()
    return float(data["rates"][target])
