"""Agent Meteo + News (Open-Meteo + NewsAPI + LLM optionnel)."""
from __future__ import annotations

import os
import re
from datetime import date, datetime
from typing import Any

import requests
from dotenv import load_dotenv

from src.agents.collector_agent.official_sources import Collector
from src.schemas import NewsEvent, WeatherNewsOutput

load_dotenv()

NEWS_API_URL = "https://newsapi.org/v2/everything"

MATIERE_QUERIES = {
    "petrole": "oil OR crude OR Brent OR petroleum OR carburant",
    "ble": "wheat OR cereal OR grain OR ble OR cerealier",
    "aluminium": "aluminum OR aluminium",
    "cuivre": "copper OR cuivre",
    "fer_acier": "steel OR iron ore OR acier",
    "plastiques": "plastics OR polyethylene OR polypropylene",
}

BULLISH = (
    "surge", "soar", "rally", "shortage", "disruption", "sanction", "war",
    "hausse", "penurie", "pénurie", "conflit", "embargo", "crise", "inflation",
)
BEARISH = (
    "drop", "fall", "slump", "glut", "surplus", "ceasefire", "baisse",
    "excedent", "excédent", "detente", "détente", "recul",
)


def _heuristic_impact(title: str, description: str = "") -> float:
    text = f"{title} {description}".lower()
    score = 0.0
    for word in BULLISH:
        if word in text:
            score += 0.25
    for word in BEARISH:
        if word in text:
            score -= 0.25
    return max(-1.0, min(1.0, score))


def _llm_score_articles(articles: list[dict[str, Any]], matieres: list[str]) -> list[float] | None:
    from src.llm import chat, llm_configured

    if not llm_configured() or not articles:
        return None
    lines = []
    for index, article in enumerate(articles[:8], start=1):
        title = article.get("title") or ""
        desc = article.get("description") or ""
        lines.append(f"{index}. {title} — {desc[:180]}")
    prompt = (
        "Tu es un analyste de marche des matieres premieres pour la Tunisie. "
        f"Matieres suivies: {', '.join(matieres) or 'petrole'}. "
        "Pour chaque article numerote, donne un score d'impact prix entre -1 "
        "(fortement baissier) et +1 (fortement haussier). "
        "Reponds UNIQUEMENT avec une liste JSON de nombres, ex: [0.3, -0.2, 0.0].\n\n"
        + "\n".join(lines)
    )
    content = chat(
        prompt,
        system="Tu reponds uniquement en JSON array de floats.",
        temperature=0.0,
        timeout=45,
    )
    if not content:
        return None
    match = re.search(r"\[[^\]]+\]", content, re.DOTALL)
    if not match:
        return None
    import json

    values = json.loads(match.group(0))
    scores = [max(-1.0, min(1.0, float(value))) for value in values]
    if len(scores) < len(articles):
        scores.extend([0.0] * (len(articles) - len(scores)))
    return scores[: len(articles)]


def _fetch_news(
    matieres: list[str],
    *,
    page_size: int = 8,
) -> tuple[list[dict[str, Any]], list[str]]:
    api_key = os.getenv("NEWS_API_KEY", "").strip()
    warnings: list[str] = []
    if not api_key:
        warnings.append(
            "NEWS_API_KEY manquante: actualites ignorees "
            "(definir la cle NewsAPI dans .env — https://newsapi.org/)"
        )
        return [], warnings

    query_parts = [MATIERE_QUERIES.get(name, name) for name in matieres] or [
        MATIERE_QUERIES["petrole"]
    ]
    query = f"({' OR '.join(query_parts)}) AND (Tunisia OR Tunisie OR subsidy OR subvention OR OPEC OR commodity)"
    try:
        response = requests.get(
            NEWS_API_URL,
            params={
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": page_size,
                "apiKey": api_key,
            },
            timeout=30,
        )
        if response.status_code == 401:
            warnings.append("NewsAPI: cle invalide (401)")
            return [], warnings
        if response.status_code == 429:
            warnings.append("NewsAPI: quota depasse (429)")
            return [], warnings
        response.raise_for_status()
        payload = response.json()
        articles = payload.get("articles") or []
        if not articles:
            warnings.append("NewsAPI: aucun article pour la requete courante")
        return articles, warnings
    except Exception as error:
        warnings.append(f"NewsAPI indisponible: {error}")
        return [], warnings


def _parse_article_date(value: str | None) -> date:
    if not value:
        return date.today()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return date.today()


def _weather_block(zone: str) -> tuple[float, list[NewsEvent], str, list[str]]:
    normalized_zone = zone.lower()
    if "nord" in normalized_zone or "north" in normalized_zone:
        location = "Bizerte"
    elif "sud" in normalized_zone or "south" in normalized_zone:
        location = "Sfax"
    elif "centre" in normalized_zone or "central" in normalized_zone:
        location = "Kairouan"
    else:
        location = "Tunis"

    errors: list[str] = []
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
    events: list[NewsEvent] = []
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
                NewsEvent(
                    date=date.fromisoformat(day),
                    titre="Risque meteo: " + ", ".join(hazards),
                    score_impact=round(daily_risk, 3),
                )
            )

    zone_label = f"{place.get('name', location)}, Tunisie"
    return score, events, zone_label, errors


def run(zone: str, matieres: list[str] | None = None) -> WeatherNewsOutput:
    """Combine Open-Meteo risk with NewsAPI headlines (LLM-scored when possible)."""
    matieres = matieres or ["petrole"]
    collection_errors: list[str] = []
    weather_score = 0.0
    events: list[NewsEvent] = []
    zone_label = zone
    sources = []

    try:
        weather_score, weather_events, zone_label, weather_errors = _weather_block(zone)
        events.extend(weather_events)
        collection_errors.extend(weather_errors)
        sources.append("Open-Meteo")
    except Exception as error:
        collection_errors.append(f"meteo: {error}")

    articles, news_warnings = _fetch_news(matieres)
    collection_errors.extend(news_warnings)
    news_mode = "none"
    if articles:
        sources.append("NewsAPI")
        llm_scores = None
        try:
            llm_scores = _llm_score_articles(articles, matieres)
        except Exception as error:
            collection_errors.append(f"LLM news: {error}")
        if llm_scores is not None:
            news_mode = "llm"
            sources.append("LLM")
            impacts = llm_scores
        else:
            news_mode = "heuristic"
            impacts = [
                _heuristic_impact(item.get("title") or "", item.get("description") or "")
                for item in articles
            ]
        for article, impact in zip(articles, impacts):
            title = (article.get("title") or "Sans titre").strip()
            source_name = (article.get("source") or {}).get("name") or "NewsAPI"
            events.append(
                NewsEvent(
                    date=_parse_article_date(article.get("publishedAt")),
                    titre=f"[{source_name}] {title}",
                    score_impact=round(float(impact), 3),
                )
            )

    news_risk = 0.0
    news_events = [event for event in events if not event.titre.startswith("Risque meteo")]
    if news_events:
        news_risk = min(1.0, max(abs(event.score_impact) for event in news_events))

    # Score agrege: meteo + intensite news (0-1)
    score = round(min(1.0, max(weather_score, 0.6 * news_risk + 0.4 * weather_score)), 3)
    source_label = " + ".join(sources) if sources else "indisponible"
    if news_mode != "none":
        source_label += f" (news={news_mode})"

    return WeatherNewsOutput(
        score_risque=score,
        events=events,
        zone=zone_label,
        source=source_label,
        is_synthetic=False,
        collection_errors=collection_errors,
    )
