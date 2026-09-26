"""Validation temporelle, entrainement quantile et prevision a trois mois."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge

from src.agents.plastics_feature_engineer_agent.agent import (
    build_feature_table,
    discover_sources,
    feature_columns,
    read_table,
)
from src.agents.plastics_predictor_agent.schema import PlasticsPredictionOutput

QUANTILES = (0.1, 0.5, 0.9)


def _model(quantile: float) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss="quantile", quantile=quantile, max_iter=120, max_leaf_nodes=15,
        min_samples_leaf=8, l2_regularization=1.0, random_state=17,
    )


def _ordered_predictions(models: list[HistGradientBoostingRegressor],
                         values: pd.DataFrame) -> np.ndarray:
    return np.sort(np.column_stack([model.predict(values) for model in models]), axis=1)


def _direction_accuracy(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.sign(actual) == np.sign(predicted)))


def _safe_float(value: float) -> float:
    return float(value) if np.isfinite(value) else float("nan")


def _ridge_model() -> Any:
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=10.0))


def _conformal_radius(scores: np.ndarray) -> float:
    """Quantile conforme fini-echantillon au niveau 80 %."""
    finite = np.asarray(scores, dtype=float)
    finite = finite[np.isfinite(finite)]
    if not len(finite):
        return 0.0
    rank = min(int(np.ceil((len(finite) + 1) * 0.8)), len(finite))
    return float(np.partition(finite, rank - 1)[rank - 1])


def _select_model(candidate_metrics: dict[str, dict[str, float]], baseline_mae: float) -> str:
    """Ne retient un candidat que s'il bat le maintien du prix actuel."""
    beating = {name: values["mae_variation"] for name, values in candidate_metrics.items()
               if values["mae_variation"] < baseline_mae}
    return min(beating, key=beating.get) if beating else "aucun_changement"


def _trend_from_prices(current_price: float, central_price: float,
                       historical_std: float) -> str:
    change = np.log(central_price / current_price)
    threshold = 0.5 * historical_std
    if change > threshold:
        return "hausse"
    if change < -threshold:
        return "baisse"
    return "stable"


def _proxy_scenarios(forecast_prices: np.ndarray, crude_index: float,
                     gas_index: float) -> dict[str, dict[str, float]]:
    """Applique les chocs aux composantes normalisees du proxy, pas au modele."""
    low, central, high = np.sort(np.asarray(forecast_prices, dtype=float))
    crude_impact = 0.70 * crude_index * 0.10
    gas_impact = 0.30 * gas_index * 0.20
    shocks = {
        "brent_hausse_10pct": crude_impact,
        "brent_baisse_10pct": -crude_impact,
        "gaz_europe_hausse_20pct": gas_impact,
    }
    return {
        name: {
            "prix_bas": float(low + impact),
            "prix_central": float(central + impact),
            "prix_haut": float(high + impact),
        }
        for name, impact in shocks.items()
    }


def _validate_and_fit(group: pd.DataFrame, columns: list[str], horizon_mois: int
                      ) -> tuple[dict[str, Any], dict[str, float], Any, dict[str, Any]]:
    target_label = f"target_delta_{horizon_mois}m"
    brent_baseline = f"baseline_brent_delta_{horizon_mois}m"
    labeled = group.loc[group[target_label].notna()].sort_values("date").reset_index(drop=True)
    if len(labeled) < 30:
        raise ValueError(f"30 observations etiquetees minimum sont requises; recu: {len(labeled)}.")
    x = labeled[columns].replace([np.inf, -np.inf], np.nan)
    y = labeled[target_label].to_numpy(dtype=float)
    splits = min(5, max(2, len(labeled) // 30))
    splitter = TimeSeriesSplit(n_splits=splits, gap=horizon_mois)
    actuals: list[float] = []
    hgb_predictions: list[np.ndarray] = []
    ridge_predictions: list[float] = []
    no_change: list[float] = []
    brent_predictions: list[float] = []
    origins: list[dict[str, Any]] = []
    last_hgb_models: list[HistGradientBoostingRegressor] = []
    last_ridge_model: Any = None
    last_validation: tuple[pd.DataFrame, np.ndarray] | None = None

    for train_indices, validation_indices in splitter.split(x):
        fold_models = [_model(q) for q in QUANTILES]
        for model in fold_models:
            model.fit(x.iloc[train_indices], y[train_indices])
        fold_predictions = _ordered_predictions(fold_models, x.iloc[validation_indices])
        ridge = _ridge_model()
        ridge.fit(x.iloc[train_indices], y[train_indices])
        ridge_fold_predictions = ridge.predict(x.iloc[validation_indices])
        actuals.extend(y[validation_indices])
        hgb_predictions.extend(fold_predictions)
        ridge_predictions.extend(ridge_fold_predictions)
        no_change.extend(np.zeros(len(validation_indices)))
        brent_predictions.extend(labeled.iloc[validation_indices][brent_baseline].to_numpy())
        for row_index in validation_indices:
            origin = labeled.iloc[row_index]
            origins.append({
                "origine": pd.Timestamp(origin["date"]).date().isoformat(),
                "date_prevue": (pd.Timestamp(origin["date"]) + pd.DateOffset(months=horizon_mois)).date().isoformat(),
                "prix_origine": float(origin["target"]),
            })
        last_validation = (x.iloc[validation_indices], y[validation_indices])
        last_hgb_models = fold_models
        last_ridge_model = ridge

    actual_array = np.asarray(actuals)
    hgb_array = np.asarray(hgb_predictions)
    ridge_array = np.asarray(ridge_predictions)
    no_change_array = np.asarray(no_change)
    brent_array = np.asarray(brent_predictions)
    finite_brent = np.isfinite(brent_array)
    brent_effective_array = np.where(finite_brent, brent_array, no_change_array)
    baseline_mae = float(mean_absolute_error(actual_array, no_change_array))
    candidate_metrics = {
        "hist_gradient_boosting": {
            "mae_variation": float(mean_absolute_error(actual_array, hgb_array[:, 1])),
            "bonnes_directions": _direction_accuracy(actual_array, hgb_array[:, 1]),
        },
        "ridge": {
            "mae_variation": float(mean_absolute_error(actual_array, ridge_array)),
            "bonnes_directions": _direction_accuracy(actual_array, ridge_array),
        },
    }
    baseline_metrics: dict[str, dict[str, float | None]] = {
        "aucun_changement": {
            "mae_variation": baseline_mae,
            "bonnes_directions": _direction_accuracy(actual_array, no_change_array),
        }
    }
    if finite_brent.any():
        baseline_metrics["variation_brent_3m"] = {
            "mae_variation": float(mean_absolute_error(actual_array, brent_effective_array)),
            "bonnes_directions": _direction_accuracy(actual_array, brent_effective_array),
        }
    selected = _select_model(candidate_metrics, baseline_mae)
    brent_baseline_mae = baseline_metrics.get("variation_brent_3m", {}).get("mae_variation")
    if isinstance(brent_baseline_mae, (int, float)) and brent_baseline_mae < baseline_mae:
        if selected == "aucun_changement" or brent_baseline_mae < candidate_metrics[selected]["mae_variation"]:
            selected = "variation_brent_3m"
    if selected == "hist_gradient_boosting":
        central_array, base_low, base_high = hgb_array[:, 1], hgb_array[:, 0], hgb_array[:, 2]
        oof_scores = np.maximum(0.0, np.maximum(base_low - actual_array, actual_array - base_high))
        final_models: Any = [_model(q) for q in QUANTILES]
        importance_model = last_hgb_models[1]
    elif selected == "ridge":
        central_array = ridge_array
        base_low = base_high = ridge_array
        oof_scores = np.abs(actual_array - ridge_array)
        final_models = _ridge_model()
        importance_model = last_ridge_model
    elif selected == "variation_brent_3m":
        central_array = brent_effective_array
        base_low = base_high = brent_effective_array
        oof_scores = np.abs(actual_array - brent_effective_array)
        final_models = None
        importance_model = None
    else:
        central_array = no_change_array
        base_low = base_high = no_change_array
        oof_scores = np.abs(actual_array - no_change_array)
        final_models = None
        importance_model = None

    train_x = labeled[columns].replace([np.inf, -np.inf], np.nan)
    if selected == "hist_gradient_boosting":
        for model in final_models:
            model.fit(train_x, y)
    elif selected == "ridge":
        final_models.fit(train_x, y)

    backtest: list[dict[str, Any]] = []
    calibrated_hits: list[bool] = []
    calibrated_count = 0
    rolling_window = 60
    for index, origin in enumerate(origins):
        origin_date = pd.Timestamp(origin["origine"])
        matured_indices = [
            score_index for score_index in range(index)
            if pd.Timestamp(origins[score_index]["date_prevue"]) <= origin_date
        ][-rolling_window:]
        past_scores = oof_scores[matured_indices]
        calibrated = len(past_scores) >= 20
        radius = _conformal_radius(past_scores) if calibrated else 0.0
        lower = float(base_low[index] - radius)
        upper = float(base_high[index] + radius)
        if calibrated:
            calibrated_hits.append(bool(lower <= actual_array[index] <= upper))
            calibrated_count += 1
        backtest.append({
            **origin,
            "reel": float(origin["prix_origine"] * np.exp(actual_array[index])),
            "prevu": float(origin["prix_origine"] * np.exp(central_array[index])),
            "bas": float(origin["prix_origine"] * np.exp(lower)),
            "haut": float(origin["prix_origine"] * np.exp(upper)),
            "couverture_evaluee": calibrated,
        })

    radius = _conformal_radius(oof_scores[-rolling_window:])
    selected_mae = float(mean_absolute_error(actual_array, central_array))
    metrics: dict[str, Any] = {
        "horizon_mois": horizon_mois,
        "validation": f"TimeSeriesSplit walk-forward, gap={horizon_mois} mois; calibration causale sur 60 residus arrives a echeance",
        "observations_validation": int(len(actual_array)),
        "modeles_candidats": candidate_metrics,
        "baselines": baseline_metrics,
        "modele_retenu": selected,
        "selection": ("Aucun candidat ne bat la baseline aucun changement; central de prevision = prix actuel."
                      if selected == "aucun_changement" else
                      f"{selected} retenu car sa MAE walk-forward bat aucun changement."),
        "modele": {
            "mae_variation": selected_mae,
            "bonnes_directions": _direction_accuracy(actual_array, central_array),
            "couverture_intervalle_10_90": (
                float(np.mean((actual_array >= base_low) & (actual_array <= base_high)))
                if selected == "hist_gradient_boosting" else None
            ),
            "couverture_calibree_walk_forward": float(np.mean(calibrated_hits)) if calibrated_hits else None,
            "points_calibration_evalues": calibrated_count,
            "niveau_calibration": 0.80,
            "rayon_conforme_log": radius,
        },
        "bat_toutes_les_baselines": bool(
            selected != "aucun_changement"
            and selected_mae < baseline_mae
            and (not finite_brent.any() or selected_mae < float(baseline_metrics["variation_brent_3m"]["mae_variation"]))
        ),
        "comparaison_baselines": (
            "Aucun modele candidat ne bat la baseline aucun changement; baseline utilisee."
            if selected == "aucun_changement"
            else "Le modele retenu bat aucun changement; les metriques Brent sont fournies separement."
        ),
        "backtest": backtest,
    }

    importances: dict[str, float] = {}
    if last_validation is not None and importance_model is not None:
        validation_x, validation_y = last_validation
        result = permutation_importance(
            importance_model, validation_x, validation_y, scoring="neg_mean_absolute_error",
            n_repeats=5, random_state=17,
        )
        importances = {
            column: float(max(0.0, score))
            for column, score in sorted(zip(columns, result.importances_mean),
                                        key=lambda item: item[1], reverse=True)
        }
    return metrics, importances, final_models, {
        "radius": radius,
        "historical_std": float(np.std(y, ddof=1)),
        "selected": selected,
    }


def predict_from_features(table: pd.DataFrame, cible_utilisee: str,
                          part_donnees_proxy: float,
                          sources_absentes: list[str] | None = None,
                          horizon_mois: int = 3,
                          ) -> list[PlasticsPredictionOutput]:
    """Entraine, valide et produit une prevision par code cible disponible."""
    columns = feature_columns(table)
    if not columns:
        raise ValueError("Aucune colonne explicative disponible.")
    results: list[PlasticsPredictionOutput] = []
    for code, group in table.groupby("code_sh", dropna=False, sort=True):
        group = group.sort_values("date").reset_index(drop=True)
        metrics, importances, model, calibration = _validate_and_fit(group, columns, horizon_mois)
        current = group.loc[group["target"].notna()].tail(1)
        if current.empty:
            continue
        current_features = current[columns].replace([np.inf, -np.inf], np.nan)
        price_now = float(current["target"].iloc[0])
        if calibration["selected"] == "hist_gradient_boosting":
            changes = _ordered_predictions(model, current_features)[0]
            changes[0] -= calibration["radius"]
            changes[2] += calibration["radius"]
        elif calibration["selected"] == "ridge":
            central_change = float(model.predict(current_features)[0])
            changes = np.array([
                central_change - calibration["radius"],
                central_change,
                central_change + calibration["radius"],
            ])
        else:
            changes = np.array([-calibration["radius"], 0.0, calibration["radius"]])
        prices = np.sort(price_now * np.exp(changes))
        trend = _trend_from_prices(
            price_now, float(prices[1]), calibration["historical_std"]
        )
        scenarios: dict[str, dict[str, float]] = {}
        if part_donnees_proxy:
            years = pd.to_datetime(group["date"]).dt.year
            crude_base = group.loc[years == 2010, "Crude_average"].mean()
            gas_base = group.loc[years == 2010, "Gas_Europe"].mean()
            if crude_base > 0 and gas_base > 0:
                crude_index = float(current["Crude_average"].iloc[0] / crude_base * 100.0)
                gas_index = float(current["Gas_Europe"].iloc[0] / gas_base * 100.0)
                scenarios = _proxy_scenarios(prices, crude_index, gas_index)
        reference_date = pd.Timestamp(current["date"].iloc[0]).date()
        limits = [
            f"Type de cible: {'proxy' if part_donnees_proxy else 'reelle'} ({cible_utilisee}).",
            f"Dernier mois disponible: {reference_date.isoformat()}.",
            "La disponibilite de publication intra-mois n'est pas prise en compte.",
        ]
        limits.extend(f"Source absente: {source}." for source in (sources_absentes or []))
        if len(group.loc[group[f"target_delta_{horizon_mois}m"].notna()]) < 60:
            limits.append("Historique court: moins de 60 observations etiquetees.")
        unit = "indice base 100 (2010)" if part_donnees_proxy else "TND/kg"
        results.append(PlasticsPredictionOutput(
            cible_utilisee=cible_utilisee,
            code_sh=str(code) if str(code) else None,
            date_reference=reference_date,
            horizon_mois=horizon_mois,
            prix_actuel=price_now,
            prix_bas=float(prices[0]),
            prix_central=float(prices[1]),
            prix_haut=float(prices[2]),
            unite=unit,
            tendance=trend,
            metriques=metrics,
            importances=importances,
            scenarios=scenarios,
            part_donnees_proxy=float(part_donnees_proxy),
            limites=limits,
        ))
    if not results:
        raise ValueError("Aucune serie cible ne contient de mois previsible.")
    return results


def run(pink_sheet: str | Path | None = None, imports: str | Path | None = None,
        customs: str | Path | None = None, usd_tnd: str | Path | None = None,
        inflation: str | Path | None = None,
    raw_dir: str | Path = "data/raw", output_dir: str | Path = "data/processed",
    horizons: tuple[int, ...] = (1, 3, 6, 12),
        ) -> list[PlasticsPredictionOutput]:
    """Execute l'ingenierie, la prevision et ecrit les contrats de sortie."""
    discovered = discover_sources(raw_dir)
    paths = {
        "pink_sheet": Path(pink_sheet) if pink_sheet else discovered["pink_sheet"],
        "imports": Path(imports) if imports else discovered["imports"],
        "customs": Path(customs) if customs else discovered["customs"],
        "usd_tnd": Path(usd_tnd) if usd_tnd else discovered["usd_tnd"],
        "inflation": Path(inflation) if inflation else discovered["inflation"],
    }
    if paths["pink_sheet"] is None or not paths["pink_sheet"].exists():
        raise FileNotFoundError(
            "Pink Sheet absent. Copiez son CSV/XLSX dans data/raw/ ou passez --pink-sheet <fichier>."
        )
    data = {name: read_table(path) if path is not None and path.exists() else None
            for name, path in paths.items()}
    feature_table, target_name, proxy_share = build_feature_table(
        data["pink_sheet"], data["imports"], data["usd_tnd"], data["inflation"], data["customs"]
    )
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    feature_table.to_csv(output_path / "features_plastiques.csv", index=False, encoding="utf-8")
    absent_sources = [name for name, path in paths.items() if path is None or not path.exists()]
    predictions = [
        prediction
        for horizon in horizons
        for prediction in predict_from_features(
            feature_table, target_name, proxy_share, absent_sources, horizon
        )
    ]
    payload = [prediction.model_dump(mode="json") for prediction in predictions]
    (output_path / "prediction_plastiques.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    history_path = output_path / "historique_previsions.csv"
    history_rows = [{
        "execution_utc": datetime.now(timezone.utc).isoformat(),
        "date_reference": prediction.date_reference.isoformat(),
        "horizon_mois": prediction.horizon_mois,
        "cible_utilisee": prediction.cible_utilisee,
        "prix_actuel": prediction.prix_actuel,
        "prix_bas": prediction.prix_bas,
        "prix_central": prediction.prix_central,
        "prix_haut": prediction.prix_haut,
        "tendance": prediction.tendance,
        "modele_retenu": prediction.metriques.get("modele_retenu", "inconnu"),
        "couverture_calibree": prediction.metriques.get("modele", {}).get(
            "couverture_calibree_walk_forward"
        ),
    } for prediction in predictions]
    history = pd.DataFrame(history_rows)
    history.to_csv(
        history_path, mode="a", header=not history_path.exists(), index=False, encoding="utf-8"
    )
    importance_rows = [
        {"code_sh": prediction.code_sh or "proxy", "feature": feature, "importance": value}
        for prediction in predictions for feature, value in prediction.importances.items()
    ]
    pd.DataFrame(importance_rows, columns=["code_sh", "feature", "importance"]).to_csv(
        output_path / "importance_features_plastiques.csv", index=False, encoding="utf-8"
    )
    print("Colonnes utilisees:", ", ".join(feature_columns(feature_table)))
    print("Horizons calcules:", ", ".join(f"{h} mois" for h in horizons))
    return predictions


def main() -> None:
    parser = argparse.ArgumentParser(description="Prevision des prix de reference des plastiques")
    parser.add_argument("--pink-sheet", help="Fichier CSV/XLSX Pink Sheet")
    parser.add_argument("--imports", help="Fichier CSV/XLSX INS COMEX")
    parser.add_argument("--customs", help="Fichier CSV/XLSX des droits de douane")
    parser.add_argument("--usd-tnd", help="Fichier CSV/XLSX USD/TND")
    parser.add_argument("--inflation", help="Fichier CSV/XLSX inflation")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--output-dir", default="data/processed")
    args = parser.parse_args()
    try:
        predictions = run(args.pink_sheet, args.imports, args.customs, args.usd_tnd,
                          args.inflation, args.raw_dir, args.output_dir)
    except (FileNotFoundError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps([item.model_dump(mode="json") for item in predictions],
                     ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()