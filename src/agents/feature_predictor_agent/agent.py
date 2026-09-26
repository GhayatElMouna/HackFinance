"""Feature engineering and a transparent price-trend baseline."""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from math import isfinite
from statistics import fmean, median, pstdev

from src.schemas import (
    CollectorOutput,
    FeaturePredictorOutput,
    FeatureRow,
    MarketDataPoint,
    MatierePremiereOutput,
    PredictionOutput,
    PriceForecastOutput,
    PriceForecastPoint,
    VariableOutput,
    WeatherNewsOutput,
)

WINDOW_SIZE = 7
MIN_TREND = 0.02
MIN_FORECAST_OBSERVATIONS = 36
VALIDATION_HORIZON = 12


def _valid_points(
    material: MatierePremiereOutput, include_synthetic: bool = False
) -> list[MarketDataPoint]:
    if material.is_synthetic and not include_synthetic:
        return []
    return sorted(
        (
            point
            for point in material.points
            if isfinite(point.prix_unitaire) and point.prix_unitaire > 0
        ),
        key=lambda point: point.date,
    )


def _fx_change(variables: list[VariableOutput], as_of) -> float:
    fx_points = sorted(
        (
            variable
            for variable in variables
            if variable.nom == "usd_tnd"
            and variable.date <= as_of
            and isfinite(variable.valeur)
            and variable.valeur > 0
        ),
        key=lambda variable: variable.date,
    )
    if len(fx_points) < 2:
        return 0.0
    previous, current = fx_points[-2:]
    return current.valeur / previous.valeur - 1


def _features_for_material(
    material: MatierePremiereOutput,
    variables: list[VariableOutput],
    weather_score: float,
    include_synthetic: bool = False,
) -> tuple[list[FeatureRow], list[float]]:
    points = _valid_points(material, include_synthetic)
    features = []
    latest_prices = []
    for index, point in enumerate(points):
        window = points[max(0, index - WINDOW_SIZE + 1) : index + 1]
        prices = [sample.prix_unitaire for sample in window]
        returns = [
            current / previous - 1
            for previous, current in zip(prices, prices[1:])
            if previous > 0
        ]
        momentum = prices[-1] / prices[0] - 1 if len(prices) > 1 else 0.0
        features.append(
            FeatureRow(
                date=point.date,
                matiere=material.matiere,
                moyenne_mobile_7j=fmean(prices),
                volatilite_glissante=pstdev(returns) if len(returns) > 1 else 0.0,
                momentum=momentum,
                variation_fx=_fx_change(variables, point.date),
                score_risque_meteo_news=weather_score,
            )
        )
        latest_prices.append(point.prix_unitaire)
    return features, latest_prices


def _predict(
    material: str, prices: list[float], is_synthetic: bool = False
) -> PredictionOutput | None:
    if len(prices) < 2:
        return None
    window = prices[-WINDOW_SIZE:]
    returns = [current / previous - 1 for previous, current in zip(window, window[1:])]
    momentum = window[-1] / window[0] - 1
    volatility = pstdev(returns) if len(returns) > 1 else 0.0
    threshold = max(MIN_TREND, volatility)

    if momentum > threshold:
        trend = "hausse"
        separation = (abs(momentum) - threshold) / threshold
    elif momentum < -threshold:
        trend = "baisse"
        separation = (abs(momentum) - threshold) / threshold
    else:
        trend = "stable_volatile"
        separation = 1 - abs(momentum) / threshold

    sample_support = min((len(window) - 1) / (WINDOW_SIZE - 1), 1.0)
    confidence = sample_support * (0.5 + 0.5 * min(max(separation, 0.0), 1.0))
    return PredictionOutput(
        matiere=material,
        tendance=trend,
        confiance=round(confidence, 4),
        is_synthetic=is_synthetic,
    )


def _next_month(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_zero_based = divmod(month_index, 12)
    month = month_zero_based + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def forecast_monthly_price(
    material: MatierePremiereOutput,
    horizon_months: int = 6,
    today: date | None = None,
) -> PriceForecastOutput:
    """Select a monthly baseline, test it on a later holdout, then forecast.

    The empirical error band describes historical validation errors, not a
    calibrated prediction interval or a guarantee of future prices.
    """
    if material.is_synthetic:
        raise ValueError("La prevision exige des observations reelles")
    if not 1 <= horizon_months <= 12:
        raise ValueError("L'horizon doit etre compris entre 1 et 12 mois")

    monthly: dict[tuple[int, int], tuple[date, float]] = {}
    for point in _valid_points(material):
        monthly[(point.date.year, point.date.month)] = (
            point.date,
            point.prix_unitaire,
        )
    observations = [monthly[key] for key in sorted(monthly)]
    if len(observations) < MIN_FORECAST_OBSERVATIONS:
        raise ValueError(
            f"Il faut au moins {MIN_FORECAST_OBSERVATIONS} mois valides; "
            f"historique disponible: {len(observations)}"
        )
    last_date = observations[-1][0]
    reference_date = today or date.today()
    max_age_days = 45 if material.matiere == "petrole" else 120
    if reference_date - last_date > timedelta(days=max_age_days):
        raise ValueError(
            f"Derniere observation trop ancienne ({last_date.isoformat()}); "
            "prevision non publiee pour une serie perimee"
        )

    prices = [value for _, value in observations]
    selection_start = len(prices) - 2 * VALIDATION_HORIZON
    selection_stop = len(prices) - VALIDATION_HORIZON
    selection_errors: dict[str, list[float]] = {
        "dernier_prix": [],
        "moyenne_3_mois": [],
    }
    for index in range(selection_start, selection_stop):
        history = prices[:index]
        actual = prices[index]
        estimates = {
            "dernier_prix": history[-1],
            "moyenne_3_mois": fmean(history[-3:]),
        }
        for candidate, estimate in estimates.items():
            selection_errors[candidate].append(abs(actual - estimate))

    method = min(
        selection_errors,
        key=lambda candidate: fmean(selection_errors[candidate]),
    )
    holdout_errors = []
    holdout_percentage_errors = []
    for index in range(len(prices) - VALIDATION_HORIZON, len(prices)):
        history = prices[:index]
        actual = prices[index]
        estimate = (
            history[-1]
            if method == "dernier_prix"
            else fmean(history[-3:])
        )
        error = abs(actual - estimate)
        holdout_errors.append(error)
        holdout_percentage_errors.append(error / actual * 100)

    last_date, last_price = observations[-1]
    forecast_anchor = max(last_date, reference_date)
    first_future_month = _next_month(
        date(forecast_anchor.year, forecast_anchor.month, 1), 1
    )
    error_band = median(holdout_errors)
    forecast_value = (
        last_price if method == "dernier_prix" else fmean(prices[-3:])
    )
    forecasts = []
    for horizon in range(1, horizon_months + 1):
        radius = error_band * horizon**0.5
        forecasts.append(
            PriceForecastPoint(
                date=_next_month(first_future_month, horizon - 1),
                prix_prevu=round(forecast_value, 2),
                borne_basse=round(max(0.0, forecast_value - radius), 2),
                borne_haute=round(forecast_value + radius, 2),
            )
        )

    unit = {
        "aluminium": "USD/tonne",
        "ble": "USD/tonne",
        "petrole": "USD/baril",
    }.get(material.matiere, "unite source")
    return PriceForecastOutput(
        matiere=material.matiere,
        source=material.source,
        unite=unit,
        derniere_observation=last_date,
        dernier_prix=round(last_price, 2),
        methode=method,
        horizon_mois=horizon_months,
        erreur_absolue_validation=round(fmean(holdout_errors), 2),
        erreur_relative_validation_pct=round(
            fmean(holdout_percentage_errors), 2
        ),
        observations_validation=len(holdout_errors),
        previsions=forecasts,
    )


def run(
    collector: CollectorOutput,
    weather_news: WeatherNewsOutput,
    *,
    include_synthetic: bool = False,
) -> FeaturePredictorOutput:
    """Build rolling features and classify observed price direction.

    Confidence is a heuristic support score, not a calibrated probability. The
    current data contract has no labeled outcomes for supervised training.
    """
    weather_score = min(max(weather_news.score_risque, 0.0), 1.0)
    all_features = []
    predictions = []
    price_forecasts = []
    for material in collector.matieres_premieres:
        features, prices = _features_for_material(
            material, collector.variables, weather_score, include_synthetic
        )
        all_features.extend(features)
        prediction = _predict(material.matiere, prices, material.is_synthetic)
        if prediction is not None:
            predictions.append(prediction)
        if not material.is_synthetic:
            try:
                price_forecasts.append(forecast_monthly_price(material))
            except ValueError:
                pass
    return FeaturePredictorOutput(
        features=all_features,
        predictions=predictions,
        price_forecasts=price_forecasts,
    )
