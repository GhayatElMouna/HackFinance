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
    _proxy_scenarios,
    _select_model,
    _trend_from_prices,
    predict_from_features,
    run,
)
from src.agents.plastics_predictor_agent.schema import PlasticsPredictionOutput
from src.dashboard.plastics_tools import (
    convert_reference_band,
    proxy_index,
    validate_uploaded_csv,
)


def _energy_data(months: int = 240) -> pd.DataFrame:
    dates = pd.date_range("2000-01-01", periods=months, freq="MS")
    step = np.arange(months, dtype=float)
    return pd.DataFrame({
        "Date": dates,
        "Brent": 35 + step * 0.12 + 4 * np.sin(step / 7),
        "Crude_average": 30 + step * 0.10 + 3 * np.sin(step / 8),
        "Gas_Europe": 5 + step * 0.025 + np.sin(step / 6),
        "Gas_US": 3 + step * 0.012 + 0.4 * np.sin(step / 5),
        "Coal": 80 + step * 0.35 + 2 * np.sin(step / 9),
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
    assert not any(column.startswith("target_delta_") for column in columns)
    assert "Coal" in original.columns
    assert "Coal" not in columns


def test_brent_baseline_uses_only_the_previous_three_months() -> None:
    energy = _energy_data()
    table, _, _ = build_feature_table(energy)
    reference = pd.Timestamp("2015-06-01")
    current = energy.loc[energy["Date"] == reference, "Brent"].iloc[0]
    previous = energy.loc[energy["Date"] == reference - pd.DateOffset(months=3), "Brent"].iloc[0]
    for horizon in (1, 3, 6, 12):
        previous_date = reference - pd.DateOffset(months=horizon)
        previous = energy.loc[energy["Date"] == previous_date, "Brent"].iloc[0]
        stored = table.loc[
            table["date"] == reference, f"baseline_brent_delta_{horizon}m"
        ].iloc[0]
        assert np.isclose(stored, np.log(current) - np.log(previous))


def test_scenarios_follow_proxy_formula_and_brent_order() -> None:
    scenarios = _proxy_scenarios(np.array([115.0, 120.0, 125.0]), 100.0, 100.0)
    up = scenarios["brent_hausse_10pct"]["prix_central"]
    center = 120.0
    down = scenarios["brent_baisse_10pct"]["prix_central"]
    assert np.isclose(up, center + 7.0)
    assert np.isclose(down, center - 7.0)
    assert up > center > down
    assert np.isclose(scenarios["gaz_europe_hausse_20pct"]["prix_central"], center + 6.0)


def test_trend_uses_forecast_price_vs_current_and_half_std_threshold() -> None:
    assert _trend_from_prices(100.0, 110.0, 0.10) == "hausse"
    assert _trend_from_prices(100.0, 90.0, 0.10) == "baisse"
    assert _trend_from_prices(100.0, 102.0, 0.10) == "stable"


def test_model_selection_falls_back_when_candidates_do_not_beat_no_change() -> None:
    candidates = {
        "hist_gradient_boosting": {"mae_variation": 0.12},
        "ridge": {"mae_variation": 0.11},
    }
    assert _select_model(candidates, 0.10) == "aucun_changement"
    assert _select_model(candidates, 0.115) == "ridge"


def test_proxy_formula_uses_independent_2010_normalization() -> None:
    assert np.isclose(proxy_index(20.0, 4.0, 10.0, 2.0), 200.0)


def test_t17_declared_price_conversion_scales_reference_band() -> None:
    band = convert_reference_band(5.0, 80.0, 100.0, 120.0, 100.0)
    assert band == {"bas": 4.0, "central": 5.0, "haut": 6.0}


def test_uploaded_csv_validation_requires_fields_and_2010_base() -> None:
    valid = pd.DataFrame({
        "Date": ["2010-01-01", "2011-01-01"],
        "Brent": [80.0, 90.0],
        "Crude_average": [75.0, 85.0],
        "Gas_Europe": [8.0, 9.0],
        "Gas_US": [4.0, 5.0],
        "Coal": [100.0, 110.0],
    })
    canonical = validate_uploaded_csv(valid)
    assert canonical["Date"].iloc[0] == pd.Timestamp("2010-01-01")
    with np.testing.assert_raises_regex(ValueError, "Colonnes requises absentes"):
        validate_uploaded_csv(valid.drop(columns=["Gas_US"]))
    with np.testing.assert_raises_regex(ValueError, "annee 2010"):
        validate_uploaded_csv(valid.iloc[[1]])


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
    (tmp_path / "pink_sheet_televerse.csv").touch()

    sources = discover_sources(tmp_path)

    assert sources["imports"].name == "plastiques_comex.csv"
    assert sources["pink_sheet"].name == "pink_sheet_televerse.csv"


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
    history_path = output_dir / "historique_previsions.csv"
    assert history_path.exists()
    assert [item.horizon_mois for item in predictions] == [1, 3, 6, 12]
    assert all(item.prix_bas <= item.prix_central <= item.prix_haut for item in predictions)
    saved = json.loads(prediction_path.read_text(encoding="utf-8"))
    assert saved[0]["cible_utilisee"] == "indice_cout_proxy_base_100_2010"
    assert saved[0]["prix_bas"] <= saved[0]["prix_central"] <= saved[0]["prix_haut"]
    assert predictions[0].date_reference.isoformat() == "2019-12-01"