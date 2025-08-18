import datetime as dt
from typing import Optional, Tuple
import requests

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

def _geocode(location: str) -> Optional[Tuple[float, float]]:
    r = requests.get(GEOCODE_URL, params={"name": location, "count": 1, "language": "en"}, timeout=15)
    r.raise_for_status()
    data = r.json()
    results = data.get("results") or []
    if not results:
        return None
    lat = results[0]["latitude"]
    lon = results[0]["longitude"]
    return float(lat), float(lon)

def get_weather_summary(location: str, days: int = 14) -> dict:
    coords = _geocode(location)
    if not coords:
        return {"avg_temp_c": 24.0, "avg_precip_mm": 2.0, "source": "default"}

    lat, lon = coords
    today = dt.date.today()
    end = today + dt.timedelta(days=max(1, days - 1))

    r = requests.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "auto",
            "start_date": today.isoformat(),
            "end_date": end.isoformat(),
        },
        timeout=15,
    )
    r.raise_for_status()
    d = r.json().get("daily", {})

    temps_max = d.get("temperature_2m_max") or []
    temps_min = d.get("temperature_2m_min") or []
    precip = d.get("precipitation_sum") or []

    if not temps_max or not temps_min:
        return {"avg_temp_c": 24.0, "avg_precip_mm": 2.0, "source": "fallback"}

    daily_means = [(hi + lo) / 2.0 for hi, lo in zip(temps_max, temps_min)]
    avg_temp = sum(daily_means) / len(daily_means)
    avg_precip = (sum(precip) / len(precip)) if precip else 0.0

    return {"avg_temp_c": round(avg_temp, 1), "avg_precip_mm": round(avg_precip, 2), "source": "open-meteo"}
