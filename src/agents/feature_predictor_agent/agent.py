"""Feature engineering and transparent price-trend classification."""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from math import isfinite
from statistics import fmean, median, pstdev

from src.schemas import (
    CollectorOutput,
    FeaturePredictorOutput,
    FeatureRow,
    FinanceLawOutput,
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
            if point.prix_unitaire is not None
            and isfinite(point.prix_unitaire)
            and point.prix_unitaire > 0
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


def _budget_for(
    matiere: str, lois: FinanceLawOutput | None
) -> tuple[float | None, float | None, float | None]:
    if lois is None:
        return None, None, None
    features = lois.features_budgetaires or {}
    return (
        features.get(f"depense_budget_mdt_{matiere}"),
        features.get(f"variation_budget_pct_{matiere}"),
        features.get(f"score_pression_budgetaire_{matiere}"),
    )


def _features_for_material(
    material: MatierePremiereOutput,
    variables: list[VariableOutput],
    weather_score: float,
    lois: FinanceLawOutput | None = None,
    include_synthetic: bool = False,
) -> tuple[list[FeatureRow], list[float]]:
    points = _valid_points(material, include_synthetic)
    depense, variation, pression = _budget_for(material.matiere, lois)
    features = []
    latest_prices = []
    for index, point in enumerate(points):
        window = points[max(0, index - WINDOW_SIZE + 1) : index + 1]
        prices = [sample.prix_unitaire for sample in window if sample.prix_unitaire]
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
                moyenne_mobile_7j=fmean(prices) if prices else None,
                volatilite_glissante=pstdev(returns) if len(returns) > 1 else 0.0,
                momentum=momentum,
                variation_fx=_fx_change(variables, point.date),
                score_risque_meteo_news=weather_score,
                depense_budget_mdt=depense,
                variation_budget_pct=variation,
                score_pression_budgetaire=pression,
            )
        )
        latest_prices.append(point.prix_unitaire)
    return features, latest_prices


def _predict(
    material: str,
    prices: list[float],
    is_synthetic: bool = False,
    lois: FinanceLawOutput | None = None,
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

    budget_influenced = False
    _, variation_budget, pression = _budget_for(material, lois)
    if pression is not None and pression >= 0.55 and variation_budget is not None:
        # Pression budgetaire haussiere renforce une hausse de prix (surcout Etat),
        # baisse de credits peut accompagner une detente — ajustement leger.
        if variation_budget > 2 and trend == "hausse":
            confidence = min(1.0, confidence + 0.08)
            budget_influenced = True
        elif variation_budget > 2 and trend == "stable_volatile":
            trend = "hausse"
            confidence = min(1.0, max(confidence, 0.55))
            budget_influenced = True
        elif variation_budget < -5 and trend == "baisse":
            confidence = min(1.0, confidence + 0.06)
            budget_influenced = True
        elif abs(variation_budget) >= 3:
            budget_influenced = True
            confidence = min(1.0, confidence + 0.03)

    sensibilites = {
        "momentum": round(abs(momentum), 4),
        "volatilite": round(volatility, 4),
    }
    if pression is not None:
        sensibilites["pression_budgetaire"] = round(pression, 4)
    if variation_budget is not None:
        sensibilites["variation_budget_pct"] = round(variation_budget, 4)

    return PredictionOutput(
        matiere=material,
        tendance=trend,
        confiance=round(confidence, 4),
        is_synthetic=is_synthetic,
        modele="baseline_momentum_budget",
        sensibilites_facteurs=sensibilites,
        budget_a_influence=budget_influenced,
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
    """Select a monthly baseline, test it on a later holdout, then forecast."""
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
        "cuivre": "USD/tonne",
        "fer_acier": "USD/dmtu",
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


def build_features(
    collector: CollectorOutput,
    weather_news: WeatherNewsOutput,
    lois_finances: FinanceLawOutput | None = None,
    include_synthetic: bool = False,
) -> list[FeatureRow]:
    weather_score = min(max(weather_news.score_risque, 0.0), 1.0)
    all_features: list[FeatureRow] = []
    for material in collector.matieres_premieres:
        features, _ = _features_for_material(
            material,
            collector.variables,
            weather_score,
            lois_finances,
            include_synthetic,
        )
        all_features.extend(features)
    return all_features


def predict_trends(
    collector: CollectorOutput,
    features: list[FeatureRow],
    lois_finances: FinanceLawOutput | None = None,
    include_synthetic: bool = False,
    horizon_mois: int = 6,
) -> FeaturePredictorOutput:
    predictions: list[PredictionOutput] = []
    price_forecasts: list[PriceForecastOutput] = []
    prices_by_material: dict[str, list[float]] = {}
    for feature in features:
        # prices reconstructed from features not available; use collector
        pass
    for material in collector.matieres_premieres:
        points = _valid_points(material, include_synthetic)
        prices = [point.prix_unitaire for point in points if point.prix_unitaire]
        prices_by_material[material.matiere] = prices
        prediction = _predict(
            material.matiere, prices, material.is_synthetic, lois_finances
        )
        if prediction is not None:
            prediction.horizon_mois = horizon_mois
            predictions.append(prediction)
        if not material.is_synthetic:
            try:
                price_forecasts.append(
                    forecast_monthly_price(material, horizon_months=horizon_mois)
                )
            except ValueError:
                pass
    return FeaturePredictorOutput(
        features=features,
        predictions=predictions,
        price_forecasts=price_forecasts,
    )


def run(
    collector: CollectorOutput,
    weather_news: WeatherNewsOutput,
    *,
    horizon_mois: int = 6,
    include_synthetic: bool = False,
    lois_finances: FinanceLawOutput | None = None,
) -> FeaturePredictorOutput:
    """Build rolling features and classify observed price direction."""
    if not 1 <= horizon_mois <= 12:
        raise ValueError("L'horizon doit etre compris entre 1 et 12 mois")
    features = build_features(
        collector, weather_news, lois_finances, include_synthetic
    )
    return predict_trends(
        collector,
        features,
        lois_finances=lois_finances,
        include_synthetic=include_synthetic,
        horizon_mois=horizon_mois,
    )
