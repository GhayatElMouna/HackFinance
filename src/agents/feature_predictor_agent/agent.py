"""Agent Feature Engineer + Predicteur (SARIMAX pour fer/acier)."""
from __future__ import annotations

from datetime import date
from typing import Optional

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

from src.data.worldbank_prices import (
    EXOG_LABELS,
    load_exog_frame,
    resolve_factor_commodities,
)
from src.schemas import (
    CollectorOutput,
    FeaturePredictorOutput,
    FeatureRow,
    ForecastPoint,
    MatierePremiereOutput,
    PredictionOutput,
    WeatherNewsOutput,
)


def _points_to_series(matiere: MatierePremiereOutput) -> pd.Series:
    df = pd.DataFrame(
        [{"date": p.date, "price": p.prix_unitaire} for p in matiere.points]
    )
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates("date")
    return df.set_index("date")["price"].asfreq("MS").interpolate()


def _project_exog(exog: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Prolonge chaque exogene par tendance lineaire recente (6 mois)."""
    future_idx = pd.date_range(
        exog.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS"
    )
    cols = {}
    for col in exog.columns:
        recent = exog[col].dropna().iloc[-6:]
        if len(recent) < 2:
            cols[col] = [float(exog[col].iloc[-1])] * horizon
            continue
        x = np.arange(len(recent))
        slope, intercept = np.polyfit(x, recent.values.astype(float), 1)
        start = len(recent)
        cols[col] = [float(intercept + slope * (start + i)) for i in range(horizon)]
    return pd.DataFrame(cols, index=future_idx)


def _classify_tendance(
    last_price: float,
    forecast: pd.Series,
    ci: pd.DataFrame,
    residuals: Optional[pd.Series] = None,
) -> tuple[str, float, float]:
    """
    Tendance basee sur le dernier point de forecast vs dernier prix observe.
    Confiance selon amplitude de variation, largeur d'IC et qualite des residus.
    """
    if last_price <= 0 or forecast.empty:
        return "stable_volatile", 0.5, 0.0

    end_price = float(forecast.iloc[-1])
    delta_pct = (end_price - last_price) / last_price

    if delta_pct > 0.015:
        tendance = "hausse"
    elif delta_pct < -0.015:
        tendance = "baisse"
    else:
        tendance = "stable_volatile"

    # Coherence directionnelle des pas mensuels
    steps = forecast.diff().dropna()
    if tendance == "hausse":
        coherence = float((steps > 0).mean()) if len(steps) else 0.5
    elif tendance == "baisse":
        coherence = float((steps < 0).mean()) if len(steps) else 0.5
    else:
        coherence = 1.0 - float((steps.abs() > last_price * 0.01).mean()) if len(steps) else 0.5

    lower_col, upper_col = ci.columns[0], ci.columns[1]
    band_end = float(ci.iloc[-1][upper_col] - ci.iloc[-1][lower_col])
    relative_band = band_end / last_price

    # Qualite d'ajustement via residus normalises
    fit_score = 0.7
    if residuals is not None and len(residuals.dropna()) > 12:
        scale = max(abs(last_price), 1.0)
        mape = float(np.nanmean(np.abs(residuals.dropna()) / scale))
        fit_score = float(np.clip(1.0 - mape * 3.0, 0.2, 1.0))

    # Horizon plus long = confiance un peu plus basse
    horizon_penalty = 0.02 * max(0, len(forecast) - 1)

    confiance = (
        0.35 * coherence
        + 0.35 * fit_score
        + 0.30 * float(np.clip(1.0 - relative_band * 1.5, 0.0, 1.0))
        - horizon_penalty
    )
    # Bonus si variation nette claire
    confiance += min(abs(delta_pct) * 2.0, 0.15)
    confiance = float(np.clip(confiance, 0.20, 0.95))

    return tendance, confiance, float(delta_pct * 100)


def _build_attributs(
    y: pd.Series,
    exog_aligned: pd.DataFrame,
    delta_pct: float,
    tendance: str,
    confiance: float,
    horizon: int,
) -> dict:
    last = float(y.iloc[-1])
    mom_3 = float(y.pct_change(3).iloc[-1] or 0.0)
    mom_12 = float(y.pct_change(12).iloc[-1] or 0.0)
    vol_6 = float(y.pct_change().tail(6).std() or 0.0)
    mm_3 = float(y.tail(3).mean())
    mm_12 = float(y.tail(12).mean())

    attrs = {
        "prix_actuel_usd": round(last, 2),
        "moyenne_3m": round(mm_3, 2),
        "moyenne_12m": round(mm_12, 2),
        "momentum_3m_pct": round(mom_3 * 100, 2),
        "momentum_12m_pct": round(mom_12 * 100, 2),
        "volatilite_6m_pct": round(vol_6 * 100, 2),
        "variation_prevue_pct": round(delta_pct, 2),
        "horizon_mois": float(horizon),
        "ecart_vs_moyenne_12m_pct": round((last / mm_12 - 1.0) * 100, 2) if mm_12 else 0.0,
    }

    for col in exog_aligned.columns:
        key = EXOG_LABELS.get(col, col)
        val = float(exog_aligned[col].iloc[-1])
        attrs[f"exog_{key}"] = round(val, 2)
        # Variation 3 mois de l'exogene
        prev = exog_aligned[col].iloc[-4] if len(exog_aligned) >= 4 else val
        if prev:
            attrs[f"exog_{key}_var_3m_pct"] = round((val / float(prev) - 1.0) * 100, 2)

    attrs["score_tendance"] = {"hausse": 1.0, "baisse": -1.0, "stable_volatile": 0.0}[tendance]
    attrs["score_confiance"] = round(confiance, 3)
    return attrs


def _forecast_sarimax(
    y: pd.Series,
    horizon: int,
    exog: Optional[pd.DataFrame] = None,
) -> PredictionOutput:
    y = y.dropna()
    if len(y) < 36:
        last = float(y.iloc[-1])
        hist = [ForecastPoint(date=d.date(), yhat=float(v)) for d, v in y.items()]
        future_idx = pd.date_range(y.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
        fc = [
            ForecastPoint(date=d.date(), yhat=last, yhat_lower=last * 0.95, yhat_upper=last * 1.05)
            for d in future_idx
        ]
        return PredictionOutput(
            matiere="fer_acier",
            tendance="stable_volatile",
            confiance=0.4,
            modele="naive",
            variation_prevue_pct=0.0,
            attributs={"prix_actuel_usd": last, "horizon_mois": float(horizon)},
            historique=hist[-60:],
            forecast=fc,
        )

    exog_aligned = None
    exog_future = None
    if exog is not None and not exog.empty:
        exog_aligned = exog.reindex(y.index).interpolate().bfill().ffill()
        # Respecter la selection utilisateur (plafond 5 pour stabilite numerique)
        keep = [c for c in exog_aligned.columns if c in EXOG_LABELS][:5]
        if not keep:
            keep = list(exog_aligned.columns)[:5]
        exog_aligned = exog_aligned[keep]
        exog_future = _project_exog(exog_aligned, horizon)

    order = (1, 1, 1)
    seasonal_order = (1, 0, 1, 12)

    try:
        model = SARIMAX(
            y,
            exog=exog_aligned,
            order=order,
            seasonal_order=seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        res = model.fit(disp=False, maxiter=300)
        pred = res.get_forecast(steps=horizon, exog=exog_future)
        mean = pred.predicted_mean
        ci = pred.conf_int(alpha=0.2)
        residuals = res.resid
    except Exception:
        model = SARIMAX(
            y,
            exog=exog_aligned,
            order=(1, 1, 1),
            seasonal_order=(0, 0, 0, 0),
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        res = model.fit(disp=False, maxiter=300)
        pred = res.get_forecast(steps=horizon, exog=exog_future)
        mean = pred.predicted_mean
        ci = pred.conf_int(alpha=0.2)
        residuals = res.resid

    hist_tail = y.iloc[-60:]
    historique = [ForecastPoint(date=d.date(), yhat=float(v)) for d, v in hist_tail.items()]
    lower_col, upper_col = ci.columns[0], ci.columns[1]
    forecast = [
        ForecastPoint(
            date=d.date(),
            yhat=float(mean.loc[d]),
            yhat_lower=float(ci.loc[d, lower_col]),
            yhat_upper=float(ci.loc[d, upper_col]),
        )
        for d in mean.index
    ]

    last_price = float(y.iloc[-1])
    tendance, confiance, delta_pct = _classify_tendance(last_price, mean, ci, residuals)
    attrs = _build_attributs(
        y,
        exog_aligned if exog_aligned is not None else pd.DataFrame(index=y.index),
        delta_pct,
        tendance,
        confiance,
        horizon,
    )

    return PredictionOutput(
        matiere="fer_acier",
        tendance=tendance,
        confiance=confiance,
        modele="sarimax",
        variation_prevue_pct=round(delta_pct, 2),
        attributs=attrs,
        historique=historique,
        forecast=forecast,
    )


def _stub_prediction(matiere: MatierePremiereOutput) -> PredictionOutput:
    points = sorted(matiere.points, key=lambda p: p.date)
    hist = [
        ForecastPoint(date=p.date, yhat=p.prix_unitaire)
        for p in points[-24:]
        if p.prix_unitaire
    ]
    last = points[-1].prix_unitaire if points else 0.0
    return PredictionOutput(
        matiere=matiere.matiere,
        tendance="stable_volatile",
        confiance=0.3,
        modele="stub",
        historique=hist,
        forecast=[ForecastPoint(date=points[-1].date if points else date.today(), yhat=last)],
    )


def _feature_rows(
    matiere: MatierePremiereOutput,
    weather_score: float,
) -> list[FeatureRow]:
    y = _points_to_series(matiere).dropna()
    if y.empty:
        return []
    rows: list[FeatureRow] = []
    for d, _price in y.iloc[-12:].items():
        window = y.loc[:d]
        mm = float(window.tail(3).mean())
        vol = float(window.tail(6).std() or 0.0)
        momentum = float(window.pct_change().tail(3).mean() or 0.0)
        rows.append(
            FeatureRow(
                date=d.date(),
                matiere=matiere.matiere,
                moyenne_mobile_7j=mm,
                volatilite_glissante=vol,
                momentum=momentum,
                variation_fx=0.0,
                score_risque_meteo_news=weather_score,
            )
        )
    return rows


def run(
    collector: CollectorOutput,
    weather_news: WeatherNewsOutput,
    horizon: int = 3,
    facteurs: list[str] | None = None,
    annee_debut: int = 2010,
) -> FeaturePredictorOutput:
    """Point d entree de l agent Feature Engineer + Predicteur."""
    horizon = max(1, min(int(horizon), 12))
    annee_debut = max(2000, min(int(annee_debut), 2024))
    start = pd.Timestamp(year=annee_debut, month=1, day=1)
    features: list[FeatureRow] = []
    predictions: list[PredictionOutput] = []

    commodities = resolve_factor_commodities(facteurs)
    exog = load_exog_frame(commodities, refresh=False) if commodities else pd.DataFrame()
    if not exog.empty:
        exog = exog.loc[exog.index >= start]

    for matiere in collector.matieres_premieres:
        features.extend(_feature_rows(matiere, weather_news.score_risque))
        if matiere.matiere == "fer_acier" and len(matiere.points) >= 12:
            y = _points_to_series(matiere)
            y = y.loc[y.index >= start]
            if len(y.dropna()) < 24:
                # Historique trop court apres filtre : elargir un peu
                y = _points_to_series(matiere).iloc[-60:]
            predictions.append(_forecast_sarimax(y, horizon=horizon, exog=exog))
        else:
            predictions.append(_stub_prediction(matiere))

    return FeaturePredictorOutput(features=features, predictions=predictions)
