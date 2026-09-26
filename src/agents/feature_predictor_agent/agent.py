from datetime import date
import math

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
from src.schemas import (
    CollectorOutput,
    FeaturePredictorOutput,
    FeatureRow,
    MatierePremiereOutput,
    PredictionOutput,
    WeatherNewsOutput,
)


def forecast_copper_prices(
    copper: MatierePremiereOutput,
    horizon_months: int = 6,
) -> pd.DataFrame:
    """Projecte le prix mensuel du cuivre par regression lineaire."""
    if copper.matiere != "cuivre":
        raise ValueError("Cette prevision est reservee a la matiere cuivre.")
    if not 1 <= horizon_months <= 12:
        raise ValueError("L'horizon doit etre compris entre 1 et 12 mois.")

    history = pd.DataFrame(
        [{"date": point.date, "prix_unitaire": point.prix_unitaire} for point in copper.points]
    ).sort_values("date")
    history = history[np.isfinite(history["prix_unitaire"])].reset_index(drop=True)
    if len(history) < 3:
        raise ValueError("Il faut au moins trois observations valides pour prevoir le cuivre.")

    prices = history["prix_unitaire"].to_numpy()
    time_steps = np.arange(len(prices)).reshape(-1, 1)
    model = LinearRegression().fit(time_steps, prices)

    future_steps = np.arange(len(prices), len(prices) + horizon_months).reshape(-1, 1)
    forecast_prices = model.predict(future_steps)
    residual_rmse = np.sqrt(mean_squared_error(prices, model.predict(time_steps)))
    forecast_dates = pd.date_range(
        start=pd.Timestamp(history["date"].iloc[-1]),
        periods=horizon_months + 1,
        freq="MS",
    )[1:]
    leads = np.arange(1, horizon_months + 1)
    uncertainty = 1.96 * residual_rmse * np.sqrt(1 + leads / len(prices))

    return pd.DataFrame(
        {
            "date": forecast_dates.date,
            "prix_prevu_tnd_kg": forecast_prices,
            "borne_basse_indicative": np.maximum(0, forecast_prices - uncertainty),
            "borne_haute_indicative": forecast_prices + uncertainty,
        }
    )
def _next_month(observation_date: date) -> date:
    if observation_date.month == 12:
        return date(observation_date.year + 1, 1, 1)
    return date(observation_date.year, observation_date.month + 1, 1)


def _trend(monthly_return: float) -> str:
    if monthly_return > 0.005:
        return "hausse"
    if monthly_return < -0.005:
        return "baisse"
    return "stable_volatile"


def _factor_sensitivities(points):
    ordered_points = sorted(points, key=lambda point: point.date)
    driver_fields = {
        "brent": "brent_usd_baril",
        "uree": "uree_usd_tonne",
    }
    sensitivities = {}
    sample_counts = {}

    for factor, field in driver_fields.items():
        returns = []
        for previous, current in zip(ordered_points, ordered_points[1:]):
            factor_previous = getattr(previous, field)
            factor_current = getattr(current, field)
            wheat_previous = previous.prix_reference_usd_tonne
            wheat_current = current.prix_reference_usd_tonne
            if _next_month(previous.date) != current.date:
                continue
            if any(value is None or value <= 0 for value in (
                factor_previous,
                factor_current,
                wheat_previous,
                wheat_current,
            )):
                continue
            returns.append((
                math.log(factor_current / factor_previous),
                math.log(wheat_current / wheat_previous),
            ))

        returns = returns[-120:]
        sample_counts[factor] = len(returns)
        if len(returns) < 36:
            continue
        factor_returns = np.asarray([row[0] for row in returns])
        wheat_returns = np.asarray([row[1] for row in returns])
        variance = float(np.var(factor_returns))
        if variance <= 1e-10:
            continue
        sensitivity = float(
            np.cov(factor_returns, wheat_returns, ddof=0)[0, 1] / variance
        )
        sensitivities[factor] = sensitivity

    return sensitivities, sample_counts


def _new_prophet_model(uncertainty_samples: int):
    from prophet import Prophet

    return Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        changepoint_prior_scale=0.05,
        interval_width=0.8,
        uncertainty_samples=uncertainty_samples,
    )


_MODEL_LABELS = {
    "prophet": "Prophet",
    "momentum3": "Momentum 3 mois",
    "persistence": "Persistance",
    "seasonal": "Saisonnier 12 mois",
}


def _backtest_models(prices: np.ndarray, dates: list[date], horizon_mois: int):
    results = {
        name: {"errors": [], "directions": [], "log_residuals": []}
        for name in _MODEL_LABELS
    }
    first_target = max(len(prices) - 24, 120 + horizon_mois)
    returns = np.diff(np.log(prices))

    for target_index in range(first_target, len(prices)):
        origin_index = target_index - horizon_mois
        if origin_index < 119:
            continue
        train = pd.DataFrame({
            "ds": pd.to_datetime(dates[:origin_index + 1]),
            "y": np.log(prices[:origin_index + 1]),
        })
        model = _new_prophet_model(uncertainty_samples=0)
        model.fit(train)
        future = model.make_future_dataframe(periods=horizon_mois, freq="MS")
        forecast = model.predict(future).iloc[-1]
        origin_price = prices[origin_index]
        actual_price = prices[target_index]
        predictions = {
            "prophet": math.exp(float(forecast["yhat"])),
            "momentum3": origin_price * math.exp(
                float(np.mean(returns[origin_index - 3:origin_index])) * horizon_mois
            ),
            "persistence": float(origin_price),
            "seasonal": float(prices[target_index - 12]),
        }
        actual_trend = _trend(math.log(actual_price / origin_price))
        for name, raw_prediction in predictions.items():
            prior_residuals = results[name]["log_residuals"]
            bias_correction = float(np.median(prior_residuals)) if len(prior_residuals) >= 3 else 0.0
            predicted_price = raw_prediction * math.exp(bias_correction)
            results[name]["errors"].append(abs(predicted_price / actual_price - 1) * 100)
            results[name]["directions"].append(
                _trend(math.log(predicted_price / origin_price)) == actual_trend
            )
            results[name]["log_residuals"].append(
                math.log(actual_price / predicted_price)
            )

    fold_count = len(next(iter(results.values()))["errors"])
    selection_count = max(1, int(fold_count * 0.75))

    def summarize(start: int, end: int):
        metrics = {}
        for name, result in results.items():
            errors = result["errors"][start:end]
            directions = result["directions"][start:end]
            residuals = np.asarray(result["log_residuals"][start:end])
            if not errors:
                continue
            bias_correction = float(np.median(residuals))
            centered_residuals = residuals - bias_correction
            metrics[name] = {
                "mape_pct": float(np.mean(errors)),
                "directional_accuracy": float(np.mean(directions)),
                "observations": float(len(errors)),
                "bias_correction_log": bias_correction,
                "residual_p10": float(np.quantile(centered_residuals, 0.1)),
                "residual_p90": float(np.quantile(centered_residuals, 0.9)),
            }
        return metrics

    selection_metrics = summarize(0, selection_count)
    holdout_metrics = summarize(selection_count, fold_count)
    return selection_metrics, holdout_metrics


def _select_direction_model(metrics: dict[str, dict[str, float]]) -> str:
    return max(
        metrics,
        key=lambda name: (
            metrics[name]["directional_accuracy"],
            -metrics[name]["mape_pct"],
        ),
    )


def apply_scenario_shocks(
    baseline_price: float,
    sensitivities: dict[str, float],
    factor_shocks_pct: dict[str, float],
    direct_price_shock_pct: float = 0.0,
) -> float:
    """Apply historical co-movement sensitivities and explicit user assumptions."""
    if direct_price_shock_pct <= -100:
        raise ValueError("Le choc direct sur le prix doit etre superieur a -100%.")
    log_change = math.log1p(direct_price_shock_pct / 100)
    for factor, shock_pct in factor_shocks_pct.items():
        if shock_pct <= -100:
            raise ValueError("Un choc de facteur doit etre superieur a -100%.")
        sensitivity = sensitivities.get(factor)
        if sensitivity is not None:
            log_change += sensitivity * math.log1p(shock_pct / 100)
    return float(baseline_price * math.exp(log_change))


def run(
    collector: CollectorOutput,
    weather_news: WeatherNewsOutput,
    horizon_mois: int = 1,
) -> FeaturePredictorOutput:
    """Prevoit le log-prix du benchmark avec Prophet et validation temporelle glissante."""
    if not 1 <= horizon_mois <= 6:
        raise ValueError("L'horizon Prophet doit etre compris entre 1 et 6 mois.")

    features_output = []
    predictions = []

    for series in collector.matieres_premieres:
        if series.is_synthetic:
            continue
        observations = sorted(
            (
                point.date,
                point.prix_reference_usd_tonne,
            )
            for point in series.points
            if point.prix_reference_usd_tonne is not None
            and point.prix_reference_usd_tonne > 0
        )
        if len(observations) < 40:
            continue

        dates = [observation[0] for observation in observations]
        prices = np.asarray([observation[1] for observation in observations], dtype=float)
        log_returns = np.diff(np.log(prices))
        if len(prices) < 132:
            continue

        selection_metrics, holdout_metrics = _backtest_models(
            prices,
            dates,
            horizon_mois,
        )
        selected_model = _select_direction_model(selection_metrics)
        train = pd.DataFrame({"ds": pd.to_datetime(dates), "y": np.log(prices)})
        model = _new_prophet_model(uncertainty_samples=300)
        model.fit(train)
        future = model.make_future_dataframe(periods=horizon_mois, freq="MS")
        forecast = model.predict(future).iloc[-1]
        target_date = forecast["ds"].date()
        prophet_price = math.exp(
            float(forecast["yhat"]) + selection_metrics["prophet"]["bias_correction_log"]
        )
        candidate_prices = {
            "prophet": prophet_price,
            "momentum3": float(
                prices[-1] * math.exp(float(np.mean(log_returns[-3:])) * horizon_mois)
            ),
            "persistence": float(prices[-1]),
            "seasonal": float(prices[horizon_mois - 13]),
        }
        selected_metrics = selection_metrics[selected_model]
        forecast_price = candidate_prices[selected_model] * math.exp(
            selected_metrics["bias_correction_log"]
        )
        forecast_return = math.log(forecast_price / float(prices[-1]))
        held_out_metrics = holdout_metrics[selected_model]
        lower_price = math.exp(
            math.log(forecast_price) + selected_metrics["residual_p10"]
        )
        upper_price = math.exp(
            math.log(forecast_price) + selected_metrics["residual_p90"]
        )
        validation_count = int(held_out_metrics["observations"])
        directional_accuracy = held_out_metrics["directional_accuracy"]
        comparison = {
            _MODEL_LABELS[name]: {
                "mape_pct": round(metrics["mape_pct"], 2),
                "directional_accuracy": round(metrics["directional_accuracy"], 4),
                "observations": metrics["observations"],
            }
            for name, metrics in holdout_metrics.items()
        }
        sensitivities, sensitivity_counts = _factor_sensitivities(series.points)
        latest_point = max(series.points, key=lambda point: point.date)

        features_output.append(
            FeatureRow(
                date=dates[-1],
                matiere=series.matiere,
                prix_reference_usd_tonne=float(prices[-1]),
                moyenne_mobile_3m=float(np.mean(prices[-3:])),
                volatilite_3m=float(np.std(log_returns[-3:])),
                momentum_3m=float(math.exp(np.sum(log_returns[-3:])) - 1),
                brent_usd_baril=latest_point.brent_usd_baril,
                uree_usd_tonne=latest_point.uree_usd_tonne,
            )
        )
        predictions.append(
            PredictionOutput(
                matiere=series.matiere,
                tendance=_trend(forecast_return),
                confiance=directional_accuracy or 0.0,
                prix_prevu=round(forecast_price, 2),
                unite="USD/tonne",
                horizon_mois=horizon_mois,
                date_cible=target_date,
                precision_historique=directional_accuracy,
                observations_selection=int(selected_metrics["observations"]),
                mape_validation_pct=held_out_metrics["mape_pct"],
                mape_baseline_validation_pct=holdout_metrics.get("momentum3", {}).get("mape_pct"),
                observations_validation=validation_count,
                source=series.source,
                prix_bas=round(lower_price, 2),
                prix_haut=round(upper_price, 2),
                prix_prophet=round(prophet_price, 2),
                modele=_MODEL_LABELS[selected_model],
                comparaison_modeles=comparison,
                sensibilites_facteurs=sensitivities,
                sensibilites_observations=sensitivity_counts,
            )
        )

    return FeaturePredictorOutput(features=features_output, predictions=predictions)
