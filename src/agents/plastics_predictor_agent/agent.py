"""Validation temporelle, entrainement quantile et prevision a trois mois."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit

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


def _validate_and_fit(group: pd.DataFrame, columns: list[str]
                      ) -> tuple[dict[str, Any], dict[str, float], list[HistGradientBoostingRegressor], np.ndarray]:
    labeled = group.loc[group["target_delta_3m"].notna()].sort_values("date").reset_index(drop=True)
    if len(labeled) < 30:
        raise ValueError(f"30 observations etiquetees minimum sont requises; recu: {len(labeled)}.")
    x = labeled[columns].replace([np.inf, -np.inf], np.nan)
    y = labeled["target_delta_3m"].to_numpy(dtype=float)
    splits = min(5, max(2, len(labeled) // 30))
    splitter = TimeSeriesSplit(n_splits=splits, gap=3)
    actuals: list[float] = []
    central_predictions: list[float] = []
    lows: list[float] = []
    highs: list[float] = []
    no_change: list[float] = []
    brent_actual: list[float] = []
    final_models: list[HistGradientBoostingRegressor] = []
    importance_model: HistGradientBoostingRegressor | None = None
    last_validation: tuple[pd.DataFrame, np.ndarray] | None = None

    for train_indices, validation_indices in splitter.split(x):
        fold_models = [_model(q) for q in QUANTILES]
        for model in fold_models:
            model.fit(x.iloc[train_indices], y[train_indices])
        fold_predictions = _ordered_predictions(fold_models, x.iloc[validation_indices])
        actuals.extend(y[validation_indices])
        lows.extend(fold_predictions[:, 0])
        central_predictions.extend(fold_predictions[:, 1])
        highs.extend(fold_predictions[:, 2])
        no_change.extend(np.zeros(len(validation_indices)))
        brent_actual.extend(labeled.iloc[validation_indices]["baseline_brent_delta_3m"].to_numpy())
        last_validation = (x.iloc[validation_indices], y[validation_indices])
        final_models = fold_models
        importance_model = fold_models[1]

    actual_array = np.asarray(actuals)
    central_array = np.asarray(central_predictions)
    low_array = np.asarray(lows)
    high_array = np.asarray(highs)
    no_change_array = np.asarray(no_change)
    brent_array = np.asarray(brent_actual)
    finite_brent = np.isfinite(brent_array)
    baseline_metrics: dict[str, dict[str, float | None]] = {
        "aucun_changement": {
            "mae_variation": float(mean_absolute_error(actual_array, no_change_array)),
            "bonnes_directions": _direction_accuracy(actual_array, no_change_array),
        }
    }
    if finite_brent.any():
        model_mae_brent_period = float(mean_absolute_error(
            actual_array[finite_brent], central_array[finite_brent]
        ))
        baseline_metrics["variation_brent_3m"] = {
            "mae_variation": float(mean_absolute_error(actual_array[finite_brent], brent_array[finite_brent])),
            "mae_modele_meme_periode": model_mae_brent_period,
            "bonnes_directions": _direction_accuracy(actual_array[finite_brent], brent_array[finite_brent]),
        }
    model_mae = float(mean_absolute_error(actual_array, central_array))
    comparisons = [model_mae < float(baseline_metrics["aucun_changement"]["mae_variation"])]
    if finite_brent.any():
        comparisons.append(model_mae_brent_period < float(
            baseline_metrics["variation_brent_3m"]["mae_variation"]
        ))
    beat_baselines = bool(comparisons and all(comparisons))
    metrics: dict[str, Any] = {
        "validation": "TimeSeriesSplit walk-forward, gap=3 mois",
        "observations_validation": int(len(actual_array)),
        "modele": {
            "mae_variation": model_mae,
            "bonnes_directions": _direction_accuracy(actual_array, central_array),
            "couverture_intervalle_10_90": float(np.mean(
                (actual_array >= low_array) & (actual_array <= high_array))),
        },
        "baselines": baseline_metrics,
        "bat_toutes_les_baselines": beat_baselines,
        "comparaison_baselines": (
            "Le modele bat les deux baselines." if beat_baselines
            else "Le modele ne bat pas toutes les baselines sur la MAE walk-forward."
        ),
    }

    train = labeled
    final_models = [_model(q) for q in QUANTILES]
    for model in final_models:
        model.fit(train[columns].replace([np.inf, -np.inf], np.nan), train["target_delta_3m"].to_numpy())

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
    threshold = 0.5 * float(np.std(y, ddof=1))
    return metrics, importances, final_models, np.array([threshold, _safe_float(model_mae)])


def _scenario_features(current: pd.DataFrame, scenario: str) -> pd.DataFrame:
    adjusted = current.copy()
    if scenario.startswith("brent"):
        variable = "Brent"
        shock = 0.10 if "hausse" in scenario else -0.10
    elif scenario.startswith("gaz_europe"):
        variable, shock = "Gas_Europe", 0.20
    else:
        return adjusted
    for column in adjusted.columns:
        if column.startswith(f"{variable}_lag_"):
            adjusted[column] = adjusted[column] * (1.0 + shock)
        elif column.startswith(f"{variable}_var_"):
            adjusted[column] = adjusted[column] + np.log1p(shock)
    return adjusted


def predict_from_features(table: pd.DataFrame, cible_utilisee: str,
                          part_donnees_proxy: float,
                          sources_absentes: list[str] | None = None
                          ) -> list[PlasticsPredictionOutput]:
    """Entraine, valide et produit une prevision par code cible disponible."""
    columns = feature_columns(table)
    if not columns:
        raise ValueError("Aucune colonne explicative disponible.")
    results: list[PlasticsPredictionOutput] = []
    for code, group in table.groupby("code_sh", dropna=False, sort=True):
        group = group.sort_values("date").reset_index(drop=True)
        metrics, importances, models, stats = _validate_and_fit(group, columns)
        current = group.loc[group["target"].notna()].tail(1)
        if current.empty:
            continue
        current_features = current[columns].replace([np.inf, -np.inf], np.nan)
        quantiles = _ordered_predictions(models, current_features)[0]
        price_now = float(current["target"].iloc[0])
        prices = price_now * np.exp(quantiles)
        prices.sort()
        central_change = float(quantiles[1])
        threshold = float(stats[0])
        trend = "hausse" if central_change > threshold else (
            "baisse" if central_change < -threshold else "stable")
        scenarios: dict[str, dict[str, float]] = {}
        for name in ("brent_hausse_10pct", "brent_baisse_10pct", "gaz_europe_hausse_20pct"):
            scenario_x = _scenario_features(current_features, name)
            scenario_prices = price_now * np.exp(_ordered_predictions(models, scenario_x)[0])
            scenario_prices.sort()
            scenarios[name] = {
                "prix_bas": float(scenario_prices[0]),
                "prix_central": float(scenario_prices[1]),
                "prix_haut": float(scenario_prices[2]),
            }
        reference_date = pd.Timestamp(current["date"].iloc[0]).date()
        limits = [
            f"Type de cible: {'proxy' if part_donnees_proxy else 'reelle'} ({cible_utilisee}).",
            f"Dernier mois disponible: {reference_date.isoformat()}.",
            "La disponibilite de publication intra-mois n'est pas prise en compte.",
        ]
        limits.extend(f"Source absente: {source}." for source in (sources_absentes or []))
        if len(group.loc[group["target_delta_3m"].notna()]) < 60:
            limits.append("Historique court: moins de 60 observations etiquetees.")
        unit = "indice base 100 (2010)" if part_donnees_proxy else "TND/kg"
        results.append(PlasticsPredictionOutput(
            cible_utilisee=cible_utilisee,
            code_sh=str(code) if str(code) else None,
            date_reference=reference_date,
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
        raw_dir: str | Path = "data/raw", output_dir: str | Path = "data/processed"
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
    predictions = predict_from_features(feature_table, target_name, proxy_share, absent_sources)
    payload = [prediction.model_dump(mode="json") for prediction in predictions]
    (output_path / "prediction_plastiques.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    importance_rows = [
        {"code_sh": prediction.code_sh or "proxy", "feature": feature, "importance": value}
        for prediction in predictions for feature, value in prediction.importances.items()
    ]
    pd.DataFrame(importance_rows, columns=["code_sh", "feature", "importance"]).to_csv(
        output_path / "importance_features_plastiques.csv", index=False, encoding="utf-8"
    )
    print("Colonnes utilisees:", ", ".join(feature_columns(feature_table)))
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