"""Dashboard interactif des prix de reference des plastiques."""

from __future__ import annotations

import json
import hashlib
import io
import importlib
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
HISTORY_PATH = ROOT / "data" / "processed" / "historique_previsions.csv"

from src.dashboard.plastics_tools import (
    PLASTIC_SH_CODES,
    convert_reference_band,
    proxy_index,
    validate_uploaded_csv,
)

st.set_page_config(page_title="Plastiques | Boussole Budgetaire", layout="wide")


@st.cache_data(show_spinner=False)
def _load_outputs_cached(features_mtime: int, prediction_mtime: int
                         ) -> tuple[pd.DataFrame, dict[int, dict[str, Any]]]:
    """Met en cache les tables jusqu'a la prochaine modification des fichiers."""
    if not FEATURES_PATH.exists() or not PREDICTION_PATH.exists():
        raise FileNotFoundError("Lancez d’abord le prédicteur Plastiques pour générer les données.")
    features = pd.read_csv(FEATURES_PATH, parse_dates=["date"])
    payload = json.loads(PREDICTION_PATH.read_text(encoding="utf-8"))
    if not payload:
        raise ValueError("Le fichier prediction_plastiques.json est vide.")
    by_horizon: dict[int, dict[str, Any]] = {}
    for prediction in payload:
        by_horizon.setdefault(int(prediction["horizon_mois"]), prediction)
    return features, by_horizon


def _load_outputs() -> tuple[pd.DataFrame, dict[int, dict[str, Any]]]:
    if not FEATURES_PATH.exists() or not PREDICTION_PATH.exists():
        raise FileNotFoundError("Lancez d’abord le prédicteur Plastiques pour générer les données.")
    return _load_outputs_cached(FEATURES_PATH.stat().st_mtime_ns, PREDICTION_PATH.stat().st_mtime_ns)


def _run_all_horizons(pink_sheet: Path | None = None) -> list[Any]:
    """Recharge les modules locaux et recalcule les horizons dans le processus Streamlit."""
    from src.agents.plastics_feature_engineer_agent import agent as feature_engineer
    from src.agents.plastics_predictor_agent import agent as predictor

    importlib.reload(feature_engineer)
    predictor = importlib.reload(predictor)
    return predictor.run(pink_sheet=pink_sheet, horizons=(1, 3, 6, 12))


def _format_value(value: float, unit: str) -> str:
    if "TND" in unit:
        return f"{value:,.3f} TND/kg"
    return f"{value:,.2f} pts"


def _feature_label(name: str) -> str:
    """Traduit les noms techniques des variables en libellés de lecture."""
    energy_labels = {
        "Brent": "Brent",
        "Crude_average": "Petrole brut moyen",
        "Gas_Europe": "Gaz Europe",
        "Gas_US": "Gaz États-Unis",
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
        "target_volatilite_6m": "Volatilité de la cible, 6 mois",
        "target_ecart_moyenne_12m": "Écart à la moyenne de la cible, 12 mois",
        "mois_sin": "Saisonnalité, sinus",
        "mois_cos": "Saisonnalité, cosinus",
        "usd_tnd": "Taux USD/TND",
        "inflation": "Inflation",
        "quantite_importee_cumulee_3m": "Importations cumulées, 3 mois",
        "quantite_importee_cumulee_12m": "Importations cumulées, 12 mois",
        "droit_douane": "Droit de douane en vigueur",
    }
    return labels.get(name, name.replace("_", " ").capitalize())


def _history_chart(features: pd.DataFrame, start: pd.Timestamp,
                   end: pd.Timestamp, logarithmic: bool) -> go.Figure:
    frame = features.sort_values("date").copy()
    frame = frame.loc[(frame["date"] >= start) & (frame["date"] <= end)]
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
        yaxis_title="Indice (2010 = 100)", yaxis_type="log" if logarithmic else "linear",
        legend={"orientation": "h", "y": 1.08},
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
        marker={"size": 8}, name="Prévision centrale",
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
        line={"color": "#263B3A", "width": 1.8}, name="Réel",
    ))
    figure.add_trace(go.Scatter(
        x=frame["date_prevue"], y=frame["prevu"], mode="lines",
        line={"color": "#C87533", "width": 1.8}, name="Prévu walk-forward",
    ))
    figure.update_layout(
        template="plotly_white", height=360, hovermode="x unified",
        margin={"l": 12, "r": 12, "t": 24, "b": 12},
        yaxis_title=prediction["unite"], legend={"orientation": "h", "y": 1.1},
    )
    return figure


def _default_values(features: pd.DataFrame) -> dict[str, float]:
    latest = features.sort_values("date").iloc[-1]
    return {name: float(latest[name]) for name in
            ("Brent", "Crude_average", "Gas_Europe", "Gas_US", "Coal")
            if name in latest and pd.notna(latest[name])}


def _read_upload(uploaded: Any, selected_horizon: int) -> None:
    raw_bytes = uploaded.getvalue()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    if st.session_state.get("last_upload_digest") == digest:
        return
    try:
        frame = pd.read_csv(io.BytesIO(raw_bytes), sep=None, engine="python")
        frame = validate_uploaded_csv(frame)
        raw_dir = ROOT / "data" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        destination = raw_dir / "pink_sheet_televerse.csv"
        frame.to_csv(destination, index=False, encoding="utf-8")
        with st.spinner("Validation du CSV et recalcul des quatre horizons..."):
            _run_all_horizons(destination)
        st.session_state["last_upload_digest"] = digest
        _load_outputs_cached.clear()
        st.session_state["upload_success_message"] = "CSV valide, enregistré et prévisions actualisées."
        st.rerun()
    except Exception as error:
        st.error(f"CSV incorrect ou calcul impossible : {error}")


def _render_simulation(features: pd.DataFrame, predictions: dict[int, dict[str, Any]],
                       selected_horizon: int, defaults: dict[str, float]) -> dict[str, Any] | None:
    st.subheader("Simuler avec mes hypothèses")
    st.caption("Prévision conditionnelle : le résultat dépend entièrement des valeurs que vous saisissez.")
    reset_col, _ = st.columns([1, 4])
    if reset_col.button("Réinitialiser aux valeurs actuelles"):
        for name, value in defaults.items():
            st.session_state[f"sim_{name}"] = value
        st.session_state["sim_month"] = int(pd.Timestamp(features["date"].max()).month)
        st.rerun()
    latest_date = pd.Timestamp(features["date"].max())
    for name, value in defaults.items():
        st.session_state.setdefault(f"sim_{name}", value)
    st.session_state.setdefault("sim_month", int(latest_date.month))
    st.session_state.setdefault("sim_horizon", selected_horizon)
    base_2010 = features.loc[features["date"].dt.year == 2010]
    crude_base = float(base_2010["Crude_average"].mean())
    gas_base = float(base_2010["Gas_Europe"].mean())
    help_text = {
        "Brent": f"USD/baril. Référence énergétique amont, hors formule directe. Valeur actuelle : {defaults['Brent']:.3f}.",
        "Crude_average": f"USD/baril. Composante à 70 % de l’indice. Valeur actuelle : {defaults['Crude_average']:.3f}.",
        "Gas_Europe": f"USD/MMBtu. Composante à 30 % de l’indice. Valeur actuelle : {defaults['Gas_Europe']:.3f}.",
        "Gas_US": f"USD/MMBtu. Contexte énergétique, hors formule directe. Valeur actuelle : {defaults['Gas_US']:.3f}.",
        "Coal": f"USD/tonne. Contexte énergétique, hors formule directe. Valeur actuelle : {defaults['Coal']:.3f}.",
    }
    with st.form("simulation_hypotheses"):
        inputs = st.columns(3)
        values: dict[str, float] = {}
        for index, name in enumerate(("Brent", "Crude_average", "Gas_Europe", "Gas_US", "Coal")):
            column = inputs[index % 3]
            values[name] = column.number_input(
                name.replace("_", " "), min_value=0.0, value=float(st.session_state[f"sim_{name}"]),
                step=0.1, format="%.3f", help=help_text[name], key=f"sim_{name}",
            )
        month = inputs[2].selectbox(
            "Mois", list(range(1, 13)), index=int(st.session_state["sim_month"]) - 1,
            help=f"Mois de référence calendaire ; la formule proxy n'applique pas de correction saisonnière. Valeur actuelle : {latest_date.month}.", key="sim_month",
        )
        horizon = inputs[0].selectbox(
            "Horizon de simulation", [1, 3, 6, 12],
            index=[1, 3, 6, 12].index(int(st.session_state["sim_horizon"])),
            help=f"Horizon en mois ; sélection actuelle : {selected_horizon} mois.", key="sim_horizon",
        )
        submitted = st.form_submit_button("Calculer", type="primary")
    result = st.session_state.get("simulation_result")
    if submitted:
        current_prediction = predictions[int(horizon)]
        simulated_index = proxy_index(values["Crude_average"], values["Gas_Europe"], crude_base, gas_base)
        base_price = float(current_prediction["prix_actuel"])
        conditional_center = simulated_index * float(current_prediction["prix_central"]) / base_price
        conditional_low = simulated_index * float(current_prediction["prix_bas"]) / base_price
        conditional_high = simulated_index * float(current_prediction["prix_haut"]) / base_price
        result = {
            "horizon": int(horizon), "mois": int(month), "indice": simulated_index,
            "bas": min(conditional_low, conditional_center, conditional_high),
            "central": conditional_center,
            "haut": max(conditional_low, conditional_center, conditional_high),
            "ecart_pct": (conditional_center / float(current_prediction["prix_central"]) - 1.0) * 100.0,
        }
        st.session_state["simulation_result"] = result
    if result:
        st.markdown(f"**Hypothèse :** {result['mois']:02d} · horizon {result['horizon']} mois")
        metrics = st.columns(5)
        metrics[0].metric("Indice saisi", f"{result['indice']:.2f}")
        metrics[1].metric("Bas", f"{result['bas']:.2f}")
        metrics[2].metric("Central", f"{result['central']:.2f}")
        metrics[3].metric("Haut", f"{result['haut']:.2f}")
        metrics[4].metric("Écart avec la prévision", f"{result['ecart_pct']:+.2f} %")
        base_prediction = predictions[result["horizon"]]
        compare = pd.DataFrame({
            "Série": ["Prévision de base", "Mes hypothèses"],
            "Bas": [base_prediction["prix_bas"], result["bas"]],
            "Central": [base_prediction["prix_central"], result["central"]],
            "Haut": [base_prediction["prix_haut"], result["haut"]],
        })
        figure = go.Figure()
        for row_index, color in ((0, "#3C78A8"), (1, "#147D6A")):
            row = compare.iloc[row_index]
            figure.add_trace(go.Scatter(
                x=[row["Bas"], row["Haut"]], y=[compare.iloc[row_index]["Série"]] * 2,
                mode="lines", line={"width": 8, "color": color}, showlegend=False,
            ))
            figure.add_trace(go.Scatter(
                x=[row["Central"]], y=[row["Série"]], mode="markers",
                marker={"size": 12, "color": color}, name=f"{row['Série']} - central",
            ))
        figure.update_layout(template="plotly_white", height=180, xaxis_title="Indice prédit", margin={"l": 8, "r": 8, "t": 12, "b": 12})
        st.plotly_chart(figure, use_container_width=True)
    return result


def _render_declaration_check(features: pd.DataFrame, prediction: dict[str, Any],
                              predictions: dict[int, dict[str, Any]]) -> None:
    st.subheader("Vérifier un prix déclaré")
    st.warning("Conversion basée sur un indice proxy ; elle doit être validée avec les données COMEX.")
    proxy_months = features.loc[features["target"].notna(), ["date", "target"]].drop_duplicates("date")
    month_keys = [date.strftime("%Y-%m") for date in pd.to_datetime(proxy_months["date"])]
    with st.form("controle_declaration"):
        left, middle, right = st.columns(3)
        code = left.selectbox("Code SH", list(PLASTIC_SH_CODES))
        month = middle.selectbox("Mois du prix de référence", month_keys, index=max(0, len(month_keys) - 1))
        ref_price = middle.number_input("Prix de référence (TND/kg)", min_value=0.001, value=1.0, step=0.1)
        declared_price = right.number_input("Prix déclaré (TND/kg)", min_value=0.001, value=1.0, step=0.1)
        selected = right.form_submit_button("Vérifier")
    if selected:
        ref_date = pd.Period(month, freq="M").to_timestamp()
        ref_row = proxy_months.loc[pd.to_datetime(proxy_months["date"]) == ref_date]
        if ref_row.empty:
            st.error("Aucun indice disponible pour le mois de référence sélectionné.")
            return
        projected = predictions[int(prediction["horizon_mois"])]
        band = convert_reference_band(
            ref_price, projected["prix_bas"], projected["prix_central"],
            projected["prix_haut"], float(ref_row["target"].iloc[0]),
        )
        st.caption(f"Code SH {code} · échéance {projected['horizon_mois']} mois")
        st.write(f"Fourchette indicative : {band['bas']:.3f} - {band['haut']:.3f} TND/kg (central {band['central']:.3f}).")
        if band["bas"] <= declared_price <= band["haut"]:
            st.success("Dans la fourchette indicative.")
        elif declared_price < band["bas"]:
            st.warning("En dessous de la fourchette : possible sous-évaluation, à vérifier.")
        else:
            st.warning("Au-dessus de la fourchette indicative, à vérifier.")


def _render_explanation(features: pd.DataFrame, prediction: dict[str, Any],
                        simulation: dict[str, Any] | None) -> None:
    st.subheader("Explication")
    series = features.loc[features["target"].notna()].sort_values("date")
    reference_date = pd.Timestamp(prediction["date_reference"])
    current = float(series["target"].iloc[-1])
    five_year = series.loc[series["date"] >= reference_date - pd.DateOffset(years=5), "target"].mean()
    prior = series.loc[series["date"] == reference_date - pd.DateOffset(months=12), "target"]
    change_12m = (current / float(prior.iloc[0]) - 1.0) * 100.0 if not prior.empty else float("nan")
    volatility = series["target"].pct_change().tail(6).std() * 100.0
    metrics = prediction.get("metriques", {})
    model_metrics = metrics.get("modele", {})
    coverage = model_metrics.get("couverture_calibree_walk_forward")
    candidates = metrics.get("modeles_candidats", {})
    baselines = metrics.get("baselines", {})
    factors = list(prediction.get("importances", {}).items())[:3]
    factor_text = (", ".join(_feature_label(name) for name, _ in factors)
                   if factors else "pétrole brut moyen (70 % de l’indice) et gaz Europe (30 %) ; baseline aucun changement retenue")
    text = (
        f"L’indice actuel est {current:.2f}, contre une moyenne d’environ cinq ans de {five_year:.2f}. "
        f"Sa variation sur douze mois est {change_12m:+.2f} % et sa volatilité mensuelle récente "
        f"(six mois) est {volatility:.2f} %.\n\n"
        f"À {prediction['horizon_mois']} mois, le central est {prediction['prix_central']:.2f}, "
        f"avec une fourchette de {prediction['prix_bas']:.2f} à {prediction['prix_haut']:.2f} ; "
        f"la tendance est {prediction['tendance']}. La méthode retenue est "
        f"{metrics.get('modele_retenu', 'inconnue')} : {metrics.get('selection', '')}"
    )
    if coverage is not None:
        text += (
            f"\n\nLes MAE walk-forward sont HGB {candidates.get('hist_gradient_boosting', {}).get('mae_variation', float('nan')):.4f}, "
            f"Ridge {candidates.get('ridge', {}).get('mae_variation', float('nan')):.4f}, "
            f"aucun changement {baselines.get('aucun_changement', {}).get('mae_variation', float('nan')):.4f}. "
            f"La couverture conforme observée est {coverage:.1%} sur les points évalués."
        )
    text += f"\n\nFacteurs principaux : {factor_text}."
    if simulation:
        text += f" La simulation conditionnelle produit un central de {simulation['central']:.2f}, soit {simulation['ecart_pct']:+.2f} % face à la prévision de base."
    text += (
        f"\n\nLimites : indice proxy et non prix COMEX ; données jusqu’au {prediction['date_reference']} ; "
        "importations COMEX et droits de douane absentes."
    )
    st.write(text)


def _render_plastics() -> None:
    st.title("Prix de référence des plastiques")
    st.caption("Prévisions conditionnelles à partir des composantes énergétiques, sans cible COMEX observée.")
    with st.expander("Importer un nouveau CSV Pink Sheet"):
        uploaded = st.file_uploader("CSV mensuel", type=["csv"], help="Colonnes requises : Date, Brent, Crude_average, Gas_Europe, Gas_US, Coal ; une observation 2010 est nécessaire.")
        if uploaded and st.button("Importer et relancer", key="import_and_run"):
            _read_upload(uploaded, 3)
    upload_message = st.session_state.pop("upload_success_message", None)
    if upload_message:
        st.success(upload_message)
    top_left, top_right = st.columns([5, 1])
    with top_right:
        if st.button("Relancer toutes les prévisions", type="primary", use_container_width=True):
            with st.spinner("Calcul des horizons 1, 3, 6 et 12 mois…"):
                try:
                    _run_all_horizons()
                    _load_outputs_cached.clear()
                    st.rerun()
                except Exception as error:
                    st.error(f"La prévision n’a pas abouti : {error}")
    try:
        features, predictions = _load_outputs()
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as error:
        st.error(str(error))
        return
    horizons = [h for h in (1, 3, 6, 12) if h in predictions]
    if not horizons:
        st.error("Aucune prévision multi-horizon trouvée. Relancez le calcul.")
        return
    selected_horizon = st.selectbox("Horizon de prévision (mois)", horizons, index=horizons.index(3) if 3 in horizons else 0)
    prediction = predictions[selected_horizon]
    target_label = "Indice proxy, base 100 en 2010" if prediction["part_donnees_proxy"] else "Prix réel importé"
    st.caption(f"{target_label} · données jusqu’au {prediction['date_reference']} · horizon {selected_horizon} mois")
    columns = st.columns(5)
    columns[0].metric("Prix actuel", _format_value(prediction["prix_actuel"], prediction["unite"]))
    columns[1].metric("Bas", _format_value(prediction["prix_bas"], prediction["unite"]))
    columns[2].metric("Central", _format_value(prediction["prix_central"], prediction["unite"]))
    columns[3].metric("Haut", _format_value(prediction["prix_haut"], prediction["unite"]))
    columns[4].metric("Tendance", prediction["tendance"].capitalize())
    metrics = prediction.get("metriques", {})
    st.markdown(f"**Cible :** `{prediction['cible_utilisee']}` · **Méthode retenue :** `{metrics.get('modele_retenu', 'inconnue')}`")

    with st.expander("Comment lire cette page"):
        st.markdown(
            "**Bas / central / haut** : intervalle prédictif conforme, central choisi par validation. "
            "**Tendance** : variation du central face au prix actuel, seuil de 0,5 écart-type historique. "
            "**Couverture** : part des résultats walk-forward contenus dans l’intervalle. "
            "**Baseline** : prédiction de variation nulle (prix inchangé). "
            "**Indice proxy** : combinaison 70 % pétrole brut moyen et 30 % gaz Europe, normalisés sur 2010."
        )

    st.subheader("Historique des composantes")
    all_dates = features["date"].dropna()
    years = list(range(2000, int(all_dates.max().year) + 1))
    start_year, end_year = st.select_slider("Période affichée", options=years, value=(years[0], years[-1]))
    logarithmic = st.checkbox("Échelle logarithmique")
    st.plotly_chart(_history_chart(features, pd.Timestamp(f"{start_year}-01-01"), pd.Timestamp(f"{end_year}-12-31"), logarithmic), use_container_width=True)
    left, right = st.columns([1.2, 1])
    with left:
        st.subheader(f"Fourchette à {selected_horizon} mois")
        st.plotly_chart(_fan_chart(features, prediction), use_container_width=True)
    with right:
        st.subheader("Scénarios")
        scenario_labels = {"brent_hausse_10pct": "Brent +10 %", "brent_baisse_10pct": "Brent -10 %", "gaz_europe_hausse_20pct": "Gaz Europe +20 %"}
        scenarios = prediction.get("scenarios", {})
        if scenarios:
            scenario_frame = pd.DataFrame([{"Scénario": scenario_labels.get(name, name), "Bas": value["prix_bas"], "Central": value["prix_central"], "Haut": value["prix_haut"]} for name, value in scenarios.items()])
            st.dataframe(scenario_frame.style.format({"Bas": "{:.2f}", "Central": "{:.2f}", "Haut": "{:.2f}"}), hide_index=True, use_container_width=True)
            st.caption("Hypothèse mécanique : choc Brent transmis à 100 % à Crude_average.")
        importance = prediction.get("importances", {})
        st.subheader("Importance des variables")
        if importance:
            importance_frame = pd.DataFrame([{"Variable": _feature_label(name), "Importance": value} for name, value in importance.items()]).sort_values("Importance").tail(12)
            figure = go.Figure(go.Bar(x=importance_frame["Importance"], y=importance_frame["Variable"], orientation="h", marker_color="#3C78A8"))
            figure.update_layout(template="plotly_white", height=380, xaxis_title="Gain de permutation MAE", yaxis_title="")
            st.plotly_chart(figure, use_container_width=True)
        else:
            st.info("La baseline aucun changement est retenue ; aucune importance de modèle n’est disponible.")

    st.subheader("Rétrovalidation walk-forward")
    backtest = _backtest_chart(prediction)
    if backtest is not None:
        st.plotly_chart(backtest, use_container_width=True)
    model_metrics = metrics.get("modele", {})
    cards = st.columns(3)
    cards[0].metric("MAE de variation", f"{model_metrics.get('mae_variation', float('nan')):.4f}")
    coverage = model_metrics.get("couverture_calibree_walk_forward")
    cards[1].metric("Couverture calibrée", f"{coverage:.1%}" if coverage is not None else "n/d")
    raw_coverage = model_metrics.get("couverture_intervalle_10_90")
    cards[2].metric("Couverture brute", f"{raw_coverage:.1%}" if raw_coverage is not None else "n/d")
    comparison = [{"Méthode": name.replace("_", " ").capitalize(), "MAE de variation": values["mae_variation"]} for name, values in {**metrics.get("modeles_candidats", {}), **metrics.get("baselines", {})}.items()]
    st.dataframe(pd.DataFrame(comparison), hide_index=True, use_container_width=True)
    st.caption(metrics.get("selection", ""))

    defaults = _default_values(features)
    simulation = _render_simulation(features, predictions, selected_horizon, defaults)
    _render_declaration_check(features, prediction, predictions)

    st.subheader("Télécharger")
    download_cols = st.columns(2)
    selected_json = json.dumps(prediction, ensure_ascii=False, indent=2)
    download_cols[0].download_button("Prévision JSON", selected_json, file_name=f"prediction_plastiques_{selected_horizon}m.json", mime="application/json")
    download_cols[1].download_button("Prévision CSV", pd.DataFrame([prediction]).drop(columns=["metriques", "importances", "scenarios", "limites"]).to_csv(index=False), file_name=f"prediction_plastiques_{selected_horizon}m.csv", mime="text/csv")
    if HISTORY_PATH.exists():
        st.subheader("Exécutions récentes")
        history = pd.read_csv(HISTORY_PATH).tail(12).sort_values("execution_utc", ascending=False)
        st.dataframe(history, hide_index=True, use_container_width=True)
    _render_explanation(features, prediction, simulation)


_render_plastics()