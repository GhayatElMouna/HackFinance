from datetime import date

from src.agents.collector_agent.official_sources import Collector
from src.schemas import WeatherNewsOutput


def run(zone: str) -> WeatherNewsOutput:
    """Fetch a 7-day Tunisia weather forecast and derive a transparent hazard score."""
    normalized_zone = zone.lower()
    if "nord" in normalized_zone or "north" in normalized_zone:
        location = "Bizerte"
    elif "sud" in normalized_zone or "south" in normalized_zone:
        location = "Sfax"
    elif "centre" in normalized_zone or "central" in normalized_zone:
        location = "Kairouan"
    else:
        location = "Tunis"

    collector = Collector()
    geocoding = collector.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": location, "count": 1, "language": "fr", "format": "json"},
    ).json()
    results = geocoding.get("results", [])
    if not results:
        raise RuntimeError(f"Localisation Open-Meteo introuvable pour {location}")
    place = results[0]
    forecast = collector.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "daily": "precipitation_sum,wind_speed_10m_max,temperature_2m_max",
            "forecast_days": 7,
            "timezone": "Africa/Tunis",
        },
    ).json()
    daily = forecast.get("daily", {})
    dates = daily.get("time", [])
    precipitation = daily.get("precipitation_sum", [])
    wind = daily.get("wind_speed_10m_max", [])
    temperature = daily.get("temperature_2m_max", [])
    if not dates or not (len(dates) == len(precipitation) == len(wind) == len(temperature)):
        raise RuntimeError("Reponse quotidienne Open-Meteo incomplete")

    score = 0.0
    events = []
    for index, day in enumerate(dates):
        rain_value = precipitation[index] or 0.0
        wind_value = wind[index] or 0.0
        heat_value = temperature[index] or 0.0
        daily_risk = min(
            1.0,
            max(rain_value / 50.0, wind_value / 100.0, max(heat_value - 35.0, 0.0) / 15.0),
        )
        score = max(score, daily_risk)
        hazards = []
        if rain_value >= 20:
            hazards.append(f"precipitations {rain_value:g} mm")
        if wind_value >= 50:
            hazards.append(f"vent {wind_value:g} km/h")
        if heat_value >= 40:
            hazards.append(f"temperature {heat_value:g} C")
        if hazards:
            events.append(
                {
                    "date": date.fromisoformat(day),
                    "titre": "Risque meteo: " + ", ".join(hazards),
                    "score_impact": round(daily_risk, 3),
                }
            )

    return WeatherNewsOutput(
        score_risque=round(score, 3),
        events=events,
        zone=f"{place.get('name', location)}, Tunisie",
        source="Open-Meteo forecast (meteo uniquement; actualites non branchees)",
        is_synthetic=False,
    )
