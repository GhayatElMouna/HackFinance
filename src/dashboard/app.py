"""Dashboard interactif des prix de reference des plastiques."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FEATURES_PATH = ROOT / "data" / "processed" / "features_plastiques.csv"
PREDICTION_PATH = ROOT / "data" / "processed" / "prediction_plastiques.json"

st.set_page_config(page_title="Plastiques | Boussole Budgetaire", layout="wide")


def _load_outputs() -> tuple[pd.DataFrame, dict[str, Any]]:
    """Charge les artefacts du dernier passage du predicteur."""
    if not FEATURES_PATH.exists() or not PREDICTION_PATH.exists():
        raise FileNotFoundError("Lancez d'abord le predicteur plastiques pour generer les donnees.")
    features = pd.read_csv(FEATURES_PATH, parse_dates=["date"])
    payload = json.loads(PREDICTION_PATH.read_text(encoding="utf-8"))
    if not payload:
        raise ValueError("Le fichier prediction_plastiques.json est vide.")
    return features, payload[0]


def _format_value(value: float, unit: str) -> str:
    if "TND" in unit:
        return f"{value:,.3f} TND/kg"
    return f"{value:,.2f} pts"


def _feature_label(name: str) -> str:
    """Traduit les noms techniques des variables en libelles de lecture."""
    energy_labels = {
        "Brent": "Brent",
        "Crude_average": "Petrole brut moyen",
        "Gas_Europe": "Gaz Europe",
        "Gas_US": "Gaz Etats-Unis",
    }
    if name in energy_labels:
        return f"{energy_labels[name]} (mois courant)"
    for key, label in energy_labels.items():
        if name.startswith(f"{key}_lag_"):
            month = name.rsplit("_", 1)[1]
            return f"{label}, retard {month} mois"
        if name.startswith(f"{key}_var_"):
            month = name.rsplit("_", 1)[1]
            return f"Variation {label}, {month} mois"
    if name.startswith("target_lag_"):
        return f"Variation cible depuis {name.rsplit('_', 1)[1]} mois"
    labels = {
        "target_volatilite_6m": "Volatilite de la cible, 6 mois",
        "target_ecart_moyenne_12m": "Ecart a la moyenne de la cible, 12 mois",
        "mois_sin": "Saisonnalite, sinus",
        "mois_cos": "Saisonnalite, cosinus",
        "usd_tnd": "Taux USD/TND",
        "inflation": "Inflation",
        "quantite_importee_cumulee_3m": "Importations cumulees, 3 mois",
        "quantite_importee_cumulee_12m": "Importations cumulees, 12 mois",
        "droit_douane": "Droit de douane en vigueur",
    }
    return labels.get(name, name.replace("_", " ").capitalize())


def _history_chart(features: pd.DataFrame) -> go.Figure:
    frame = features.sort_values("date").copy()
    frame = frame.loc[frame["date"] >= "2000-01-01"]
    figure = go.Figure()
    if "target" in frame:
        figure.add_trace(go.Scatter(
            x=frame["date"], y=frame["target"], name="Indice plastiques",
            line={"color": "#147D6A", "width": 2.8},
        ))
    base_mask = frame["date"].dt.year == 2010
    for column, label, color in (
        ("Crude_average", "Petrole brut moyen, base 100", "#C87533"),
        ("Gas_Europe", "Gaz Europe, base 100", "#3C78A8"),
    ):
        if column not in frame:
            continue
        base = frame.loc[base_mask, column].mean()
        if pd.notna(base) and base > 0:
            figure.add_trace(go.Scatter(
                x=frame["date"], y=frame[column] / base * 100.0,
                name=label, line={"color": color, "width": 1.8},
            ))
    figure.update_layout(
        template="plotly_white", height=410, hovermode="x unified",
        margin={"l": 12, "r": 12, "t": 28, "b": 12},
        yaxis_title="Indice (2010 = 100)", legend={"orientation": "h", "y": 1.08},
    )
    return figure


def _fan_chart(features: pd.DataFrame, prediction: dict[str, Any]) -> go.Figure:
    date_reference = pd.Timestamp(prediction["date_reference"])
    history = features.loc[
        (features["date"] <= date_reference) & features["target"].notna()
    ].sort_values("date").tail(24)
    forecast_date = date_reference + pd.DateOffset(months=int(prediction["horizon_mois"]))
    x_forecast = [date_reference, forecast_date]
    figure = go.Figure()
    figure.add_trace(go.Scatter(
        x=x_forecast, y=[prediction["prix_haut"]] * 2, mode="lines",
        line={"width": 0}, showlegend=False, hoverinfo="skip",
    ))
    figure.add_trace(go.Scatter(
        x=x_forecast, y=[prediction["prix_bas"]] * 2, mode="lines",
        line={"width": 0}, fill="tonexty", fillcolor="rgba(20,125,106,0.18)",
        name="Fourchette calibree 80 %",
    ))
    figure.add_trace(go.Scatter(
        x=history["date"], y=history["target"], mode="lines+markers",
        marker={"size": 4}, line={"color": "#263B3A", "width": 2}, name="Historique observe",
    ))
    figure.add_trace(go.Scatter(
        x=[date_reference, forecast_date],
        y=[prediction["prix_actuel"], prediction["prix_central"]],
        mode="lines+markers", line={"color": "#147D6A", "width": 2.6, "dash": "dash"},
        marker={"size": 8}, name="Prevision centrale",
    ))
    figure.update_layout(
        template="plotly_white", height=380, hovermode="x unified",
        margin={"l": 12, "r": 12, "t": 28, "b": 12},
        yaxis_title=prediction["unite"], legend={"orientation": "h", "y": 1.1},
    )
    return figure


def _backtest_chart(prediction: dict[str, Any]) -> go.Figure | None:
    records = prediction.get("metriques", {}).get("backtest", [])
    if not records:
        return None
    frame = pd.DataFrame(records)
    frame["date_prevue"] = pd.to_datetime(frame["date_prevue"])
    figure = go.Figure()
    figure.add_trace(go.Scatter(
        x=frame["date_prevue"], y=frame["haut"], mode="lines",
        line={"width": 0}, showlegend=False, hoverinfo="skip",
    ))
    figure.add_trace(go.Scatter(
        x=frame["date_prevue"], y=frame["bas"], mode="lines",
        line={"width": 0}, fill="tonexty", fillcolor="rgba(60,120,168,0.14)",
        name="Intervalle walk-forward",
    ))
    figure.add_trace(go.Scatter(
        x=frame["date_prevue"], y=frame["reel"], mode="lines",
        line={"color": "#263B3A", "width": 1.8}, name="Reel",
    ))
    figure.add_trace(go.Scatter(
        x=frame["date_prevue"], y=frame["prevu"], mode="lines",
        line={"color": "#C87533", "width": 1.8}, name="Prevu walk-forward",
    ))
    figure.update_layout(
        template="plotly_white", height=360, hovermode="x unified",
        margin={"l": 12, "r": 12, "t": 24, "b": 12},
        yaxis_title=prediction["unite"], legend={"orientation": "h", "y": 1.1},
    )
    return figure


def _render_plastics() -> None:
    st.title("Prix de reference des plastiques")
    top_left, top_right = st.columns([5, 1])
    with top_right:
        if st.button("Relancer la prevision", type="primary", use_container_width=True):
            from src.agents.plastics_predictor_agent.agent import run

            with st.spinner("Calcul walk-forward et mise a jour des sorties..."):
                try:
                    run()
                    st.rerun()
                except Exception as error:
                    st.error(f"La prevision n'a pas abouti : {error}")
    try:
        features, prediction = _load_outputs()
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as error:
        st.error(str(error))
        return

    target_label = "Indice proxy, base 100 en 2010" if prediction["part_donnees_proxy"] else "Prix reel importe"
    st.caption(
        f"{target_label} · Donnees jusqu'au {prediction['date_reference']} · "
        f"Horizon {prediction['horizon_mois']} mois"
    )
    unit = prediction["unite"]
    columns = st.columns(5)
    columns[0].metric("Prix actuel", _format_value(prediction["prix_actuel"], unit))
    columns[1].metric("Bas", _format_value(prediction["prix_bas"], unit))
    columns[2].metric("Central", _format_value(prediction["prix_central"], unit))
    columns[3].metric("Haut", _format_value(prediction["prix_haut"], unit))
    columns[4].metric("Tendance", prediction["tendance"].capitalize())

    metrics = prediction.get("metriques", {})
    chosen = metrics.get("modele_retenu", "inconnu")
    st.markdown(f"**Cible :** `{prediction['cible_utilisee']}` · **Methode retenue :** `{chosen}`")

    st.subheader("Historique des composantes")
    st.plotly_chart(_history_chart(features), use_container_width=True)

    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("Fourchette a 3 mois")
        st.plotly_chart(_fan_chart(features, prediction), use_container_width=True)
    with right:
        st.subheader("Scenarios")
        scenario_labels = {
            "brent_hausse_10pct": "Brent +10 %",
            "brent_baisse_10pct": "Brent -10 %",
            "gaz_europe_hausse_20pct": "Gaz Europe +20 %",
        }
        scenarios = prediction.get("scenarios", {})
        if scenarios:
            scenario_frame = pd.DataFrame([
                {
                    "Scenario": scenario_labels.get(name, name),
                    "Bas": values["prix_bas"],
                    "Central": values["prix_central"],
                    "Haut": values["prix_haut"],
                }
                for name, values in scenarios.items()
            ])
            st.dataframe(
                scenario_frame.style.format({"Bas": "{:.2f}", "Central": "{:.2f}", "Haut": "{:.2f}"}),
                hide_index=True, use_container_width=True,
            )
            st.caption(
                "Chocs mecaniques sur les composantes normalisees. Hypothese : "
                "un choc Brent est transmis a 100 % a Crude_average."
            )
        else:
            st.info("Les scenarios de l'indice proxy ne s'appliquent pas a une cible COMEX directe.")

        st.subheader("Importance des variables")
        importance = prediction.get("importances", {})
        if importance:
            importance_frame = pd.DataFrame([
                {"Variable": _feature_label(name), "Importance": value}
                for name, value in importance.items()
            ]).sort_values("Importance", ascending=True).tail(12)
            figure = go.Figure(go.Bar(
                x=importance_frame["Importance"], y=importance_frame["Variable"],
                orientation="h", marker_color="#3C78A8",
            ))
            figure.update_layout(
                template="plotly_white", height=390, margin={"l": 12, "r": 12, "t": 15, "b": 12},
                xaxis_title="Gain de permutation sur la MAE", yaxis_title="",
            )
            st.plotly_chart(figure, use_container_width=True)
        else:
            st.info("Pas d'importance de variables : la baseline aucun changement a ete retenue.")

    st.subheader("Backtest walk-forward")
    backtest = _backtest_chart(prediction)
    if backtest is not None:
        st.plotly_chart(backtest, use_container_width=True)
        model_metrics = metrics.get("modele", {})
        first, second, third = st.columns(3)
        first.metric("MAE variation", f"{model_metrics.get('mae_variation', float('nan')):.4f}")
        coverage = model_metrics.get("couverture_calibree_walk_forward")
        second.metric("Couverture calibree", f"{coverage:.1%}" if coverage is not None else "n/d")
        raw_coverage = model_metrics.get("couverture_intervalle_10_90")
        third.metric("Couverture brute", f"{raw_coverage:.1%}" if raw_coverage is not None else "n/d")
        candidates = metrics.get("modeles_candidats", {})
        baselines = metrics.get("baselines", {})
        comparison = []
        for name, result in candidates.items():
            comparison.append({"Methode": name.replace("_", " ").capitalize(), "MAE variation": result["mae_variation"]})
        for name, result in baselines.items():
            comparison.append({"Methode": name.replace("_", " ").capitalize(), "MAE variation": result["mae_variation"]})
        if comparison:
            st.dataframe(pd.DataFrame(comparison), hide_index=True, use_container_width=True)
        st.caption(metrics.get("selection", ""))
    else:
        st.info("Le predicteur n'a pas inclus les points de backtest dans le JSON.")

    limits = prediction.get("limites", [])
    missing_sources = [item for item in limits if "Source absente" in item]
    st.subheader("Limites")
    st.info(
        f"Indice proxy (pas un prix COMEX observe). Donnees Pink Sheet jusqu'au "
        f"{prediction['date_reference']}. Importations COMEX et droits de douane absents. "
        + (" ".join(missing_sources) if missing_sources else "")
    )


def _render_existing_dashboard() -> None:
    from src.graph import run_pipeline

    st.title("Boussole Budgetaire")
    materials = st.multiselect(
        "Matieres premieres", ["ble", "petrole", "plastiques", "aluminium"],
        default=["ble", "petrole"],
    )
    if st.button("Lancer le pipeline"):
        result = run_pipeline(materials, "zones cerealieres nord Tunisie")
        st.subheader("Predictions")
        st.write(result.feature_predictor.predictions)
        st.subheader("Explications")
        st.write(result.explanations)


page = st.sidebar.radio("Vue", ["Plastiques", "Pipeline multi-matieres"], index=0)
if page == "Plastiques":
    _render_plastics()
else:
    _render_existing_dashboard()