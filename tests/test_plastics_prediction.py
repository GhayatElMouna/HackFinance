"""Tests hors ligne du pipeline prediction plastiques."""

import json

import numpy as np
import pandas as pd

from src.agents.plastics_feature_engineer_agent.agent import (
    build_feature_table,
    discover_sources,
    feature_columns,
)
from src.agents.plastics_predictor_agent.agent import (
    _model,
    _ordered_predictions,
    predict_from_features,
    run,
)
from src.agents.plastics_predictor_agent.schema import PlasticsPredictionOutput


def _energy_data(months: int = 240) -> pd.DataFrame:
    dates = pd.date_range("2000-01-01", periods=months, freq="MS")
    step = np.arange(months, dtype=float)
    return pd.DataFrame({
        "Date": dates,
        "Brent": 35 + step * 0.12 + 4 * np.sin(step / 7),
        "Crude_average": 30 + step * 0.10 + 3 * np.sin(step / 8),
        "Gas_Europe": 5 + step * 0.025 + np.sin(step / 6),
        "Gas_US": 3 + step * 0.012 + 0.4 * np.sin(step / 5),
        "Saison": dates.month,
    })


def test_features_at_date_do_not_depend_on_future_rows() -> None:
    energy = _energy_data()
    original, _, _ = build_feature_table(energy)
    cutoff = pd.Timestamp("2015-06-01")
    changed = energy.copy()
    future = changed["Date"] > cutoff
    changed.loc[future, ["Brent", "Crude_average", "Gas_Europe", "Gas_US"]] *= 1.4
    revised, _, _ = build_feature_table(changed)
    columns = feature_columns(original)
    before = original.loc[original["date"] == cutoff, columns].to_numpy(dtype=float)
    after = revised.loc[revised["date"] == cutoff, columns].to_numpy(dtype=float)
    np.testing.assert_allclose(before, after, equal_nan=True)
    assert "target_delta_3m" not in columns


def test_imports_switch_target_and_keep_code_series() -> None:
    energy = _energy_data(96)
    dates = pd.date_range("2000-01-01", periods=96, freq="MS")
    imports = pd.DataFrame({
        "Date": list(dates) * 2,
        "Code SH": ["3901"] * len(dates) + ["3902"] * len(dates),
        "Valeur": [10000 + i * 30 for i in range(len(dates))] * 2,
        "Quantite": [1000 + i * 2 for i in range(len(dates))] * 2,
    })
    table, target, proxy_share = build_feature_table(energy, imports_data=imports)
    assert target == "prix_unitaire_importation"
    assert proxy_share == 0.0
    assert set(table["code_sh"]) == {"3901", "3902"}
    assert table.loc[table["code_sh"] == "3901", "target"].notna().any()


def test_source_discovery_does_not_mistake_comex_for_pink_sheet(tmp_path) -> None:
    (tmp_path / "plastiques_comex.csv").touch()
    (tmp_path / "pinksheet_mensuelle.xlsx").touch()

    sources = discover_sources(tmp_path)

    assert sources["imports"].name == "plastiques_comex.csv"
    assert sources["pink_sheet"].name == "pinksheet_mensuelle.xlsx"


def test_quantile_order_and_json_contract() -> None:
    energy = _energy_data()
    table, target, proxy_share = build_feature_table(energy)
    values = pd.DataFrame({"x": [0.0, 1.0, 2.0]})
    models = [_model(quantile) for quantile in (0.1, 0.5, 0.9)]
    for model, offset in zip(models, (2.0, 0.0, -2.0)):
        model.fit(values, np.array([0.0, 1.0, 2.0]) + offset)
    assert np.all(np.diff(_ordered_predictions(models, values), axis=1) >= 0)

    prediction = predict_from_features(table, target, proxy_share)[0]
    payload = prediction.model_dump(mode="json")
    serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    restored = PlasticsPredictionOutput.model_validate_json(serialized)
    assert restored.cible_utilisee == "indice_cout_proxy_base_100_2010"
    assert restored.prix_bas <= restored.prix_central <= restored.prix_haut
    assert restored.part_donnees_proxy == 1.0
    assert restored.metriques["modele"]["couverture_intervalle_10_90"] >= 0.0


def test_cli_pipeline_writes_feature_prediction_and_importance_files(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "processed"
    raw_dir.mkdir()
    _energy_data().to_csv(raw_dir / "pink_sheet.csv", index=False)

    predictions = run(raw_dir=raw_dir, output_dir=output_dir)

    features_path = output_dir / "features_plastiques.csv"
    prediction_path = output_dir / "prediction_plastiques.json"
    importance_path = output_dir / "importance_features_plastiques.csv"
    assert features_path.exists()
    assert prediction_path.exists()
    assert importance_path.exists()
    saved = json.loads(prediction_path.read_text(encoding="utf-8"))
    assert saved[0]["cible_utilisee"] == "indice_cout_proxy_base_100_2010"
    assert saved[0]["prix_bas"] <= saved[0]["prix_central"] <= saved[0]["prix_haut"]
    assert predictions[0].date_reference.isoformat() == "2019-12-01"