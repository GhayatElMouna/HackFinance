import streamlit as st
import pandas as pd

st.set_page_config(page_title="Prevision du ble", layout="wide")

from src.graph import run_pipeline
from src.agents.feature_predictor_agent.agent import apply_scenario_shocks
from src.agents.provisioning_agent import (
    calculate_provisioning_plan,
    load_latest_tunisia_wheat_baseline,
)


@st.cache_data
def load_provisioning_baseline():
    return load_latest_tunisia_wheat_baseline()

st.title("Aide a la decision pour le ble")
st.caption("Prix de reference international et estimation du besoin d'achat en Tunisie")
price_horizon_months = st.select_slider(
    "Dans combien de temps souhaitez-vous estimer le prix ?",
    options=[1, 3, 6],
    value=1,
    format_func=lambda months: f"{months} mois",
)
factor_labels = {"brent": "Brent", "uree": "Uree"}
with st.expander("Tester des hypotheses de marche", expanded=False):
    selected_factors = st.multiselect(
        "Facteurs a modifier",
        options=list(factor_labels),
        default=list(factor_labels),
        format_func=lambda factor: factor_labels[factor],
    )
    factor_shocks_input = {
        factor: st.slider(
            f"Variation supposee du {factor_labels[factor]} (%)",
            -50,
            50,
            0,
            5,
            key=f"shock_{factor}",
        )
        for factor in selected_factors
    }
    direct_risk_shock = st.slider(
        "Variation directe liee au risque meteo, geopolitique ou transport (%)",
        -30,
        30,
        0,
        5,
    )
    st.caption(
        "Ces valeurs servent a tester des situations possibles. Elles ne garantissent pas "
        "l'effet reel de ces evenements sur le prix."
    )

with st.expander("Plan d'approvisionnement", expanded=False):
    try:
        provisioning_baseline = load_provisioning_baseline()
    except (FileNotFoundError, ValueError) as error:
        provisioning_baseline = None
        st.warning(str(error))

    if provisioning_baseline:
        st.metric(
            f"Besoin annuel de reference ({provisioning_baseline.year})",
            f"{provisioning_baseline.domestic_supply_tonnes:,.0f} tonnes",
        )
        st.caption(
            f"En {provisioning_baseline.year}: alimentation "
            f"{provisioning_baseline.food_use_tonnes:,.0f} t, production "
            f"{provisioning_baseline.production_tonnes:,.0f} t et importations "
            f"{provisioning_baseline.import_tonnes:,.0f} t. "
            "Ces donnees annuelles ne correspondent pas aux stocks disponibles aujourd'hui."
        )

    planning_months = st.slider("Periode a couvrir (mois)", 1, 12, 3)
    buffer_days = st.slider("Reserve de securite souhaitee (jours)", 0, 180, 30, 5)
    stock_col, arrivals_col, harvest_col = st.columns(3)
    with stock_col:
        current_stocks = st.number_input(
            "Stock utilisable aujourd'hui (tonnes)", min_value=0.0, value=None,
            placeholder="A renseigner", step=1000.0, format="%.0f",
        )
    with arrivals_col:
        scheduled_arrivals = st.number_input(
            "Arrivages deja commandes (tonnes)", min_value=0.0, value=None,
            placeholder="A renseigner", step=1000.0, format="%.0f",
        )
    with harvest_col:
        expected_harvest = st.number_input(
            "Recolte attendue pendant la periode (tonnes)", min_value=0.0, value=None,
            placeholder="A renseigner", step=1000.0, format="%.0f",
        )
    fx_col, premium_col = st.columns(2)
    with fx_col:
        usd_tnd = st.number_input(
            "Taux de change USD/TND (facultatif)", min_value=0.0001, value=None,
            placeholder="A renseigner", step=0.01, format="%.4f",
        )
    with premium_col:
        landed_premium_pct = st.number_input(
            "Surcout estime de transport et assurance (%) (facultatif)", min_value=0.0, value=None,
            placeholder="A renseigner", step=1.0, format="%.1f",
        )

if st.button("Calculer la prevision"):
    result = run_pipeline(
        ["ble"],
        "zones cerealieres nord Tunisie",
        horizon_mois=price_horizon_months,
    )
    st.subheader("Resultat")
    wheat_scenario_rows = []
    if result.feature_predictor.predictions:
        for prediction in result.feature_predictor.predictions:
            trend_labels = {
                "hausse": "Hausse attendue",
                "baisse": "Baisse attendue",
                "stable_volatile": "Stable ou incertaine",
            }
            price_col, trend_col, range_col = st.columns(3)
            price_col.metric(
                "Prix international estime",
                f"{prediction.prix_prevu:,.2f} {prediction.unite}",
            )
            trend_col.metric(
                "Tendance attendue",
                trend_labels.get(prediction.tendance, prediction.tendance),
            )
            range_col.metric(
                "Fourchette indicative",
                f"{prediction.prix_bas:,.2f} - {prediction.prix_haut:,.2f}",
            )
            st.caption(
                f"Estimation pour {prediction.date_cible:%m/%Y}, en USD par tonne. "
                "Hors transport, assurance et conditions du contrat tunisien."
            )
            if prediction.precision_historique is not None:
                correct_count = round(
                    prediction.precision_historique * prediction.observations_validation
                )
            else:
                correct_count = 0
            if prediction.precision_historique is not None and prediction.precision_historique <= 0.5:
                st.warning(
                    f"Signal peu fiable: la tendance etait correcte dans {correct_count} cas sur "
                    f"{prediction.observations_validation} tests recents. Ne basez pas un achat "
                    "uniquement sur cette estimation."
                )
            else:
                st.caption(
                    f"Dans le test historique recent, la direction etait correcte dans "
                    f"{correct_count} cas sur {prediction.observations_validation}."
                )
            available_factors = {
                factor: sensitivity
                for factor, sensitivity in prediction.sensibilites_facteurs.items()
                if factor in selected_factors
            }
            scenario_rows = [{
                "Situation": "Reference actuelle",
                "Hypotheses": "Aucun choc",
                "Prix estime (USD/tonne)": prediction.prix_prevu,
                "Ecart vs reference (%)": 0.0,
            }]
            scenario_specs = []
            if any(factor_shocks_input.values()) or direct_risk_shock:
                scenario_specs = [
                    ("Scenario saisi", factor_shocks_input, direct_risk_shock),
                    (
                        "Chocs inverses",
                        {factor: -shock for factor, shock in factor_shocks_input.items()},
                        -direct_risk_shock,
                    ),
                ]
            for label, requested_shocks, risk_shock in scenario_specs:
                factor_shocks = {
                    factor: shock
                    for factor, shock in requested_shocks.items()
                    if factor in available_factors
                }
                scenario_price = apply_scenario_shocks(
                    prediction.prix_prevu,
                    available_factors,
                    factor_shocks,
                    risk_shock,
                )
                assumptions = [
                    f"{factor_labels[factor]} {shock:+d}%"
                    for factor, shock in factor_shocks.items()
                ]
                if risk_shock:
                    assumptions.append(f"choc direct {risk_shock:+d}% (hypothese)")
                unavailable = set(requested_shocks) - set(available_factors)
                if unavailable:
                    assumptions.append(
                        "sensibilite indisponible: "
                        + ", ".join(factor_labels[factor] for factor in unavailable)
                    )
                scenario_rows.append({
                    "Situation": "Hypothese choisie" if label == "Scenario saisi" else "Hypothese inverse",
                    "Hypotheses": ", ".join(assumptions) or "Aucun facteur disponible",
                    "Prix estime (USD/tonne)": scenario_price,
                    "Ecart vs reference (%)": (scenario_price / prediction.prix_prevu - 1) * 100,
                })
            if prediction.matiere == "ble":
                wheat_scenario_rows = scenario_rows
            st.subheader("Effet des hypotheses sur le prix")
            st.dataframe(pd.DataFrame(scenario_rows), hide_index=True, use_container_width=True)
            if scenario_specs:
                st.bar_chart(
                    pd.DataFrame(scenario_rows),
                    x="Situation",
                    y="Prix estime (USD/tonne)",
                )
            st.caption(
                "Les hypotheses sont basees sur les evolutions passees. Elles ne prouvent pas "
                "qu'un facteur provoque directement une variation du prix."
            )
    else:
        st.warning("Aucune prevision: aucun historique mensuel reel et exploitable n'a ete charge.")

    wheat = next(
        (series for series in result.collector.matieres_premieres if series.matiere == "ble"),
        None,
    )
    wheat_prediction = next(
        (prediction for prediction in result.feature_predictor.predictions if prediction.matiere == "ble"),
        None,
    )
    wheat_points = [
        {
            "Date": point.date,
            "Prix de reference (USD/tonne)": point.prix_reference_usd_tonne,
        }
        for point in wheat.points
        if point.prix_reference_usd_tonne is not None
    ] if wheat else []
    if wheat_points and wheat_prediction:
        history = sorted(wheat_points, key=lambda point: point["Date"])[-120:]
        chart_rows = [
            {
                "Date": point["Date"],
                "Cours observe": point["Prix de reference (USD/tonne)"],
                "Prevision retenue": None,
                "Borne basse 80%": None,
                "Borne haute 80%": None,
                "Scenario saisi": None,
                "Chocs inverses": None,
            }
            for point in history
        ]
        latest_price = history[-1]["Prix de reference (USD/tonne)"]
        for column in chart_rows[-1]:
            if column != "Date":
                chart_rows[-1][column] = latest_price
        scenario_by_name = {
            row["Situation"]: row["Prix estime (USD/tonne)"]
            for row in wheat_scenario_rows
        }
        chart_rows.append({
            "Date": wheat_prediction.date_cible,
            "Cours observe": None,
            "Prevision retenue": wheat_prediction.prix_prevu,
            "Borne basse 80%": wheat_prediction.prix_bas,
            "Borne haute 80%": wheat_prediction.prix_haut,
            "Scenario saisi": scenario_by_name.get("Hypothese choisie"),
            "Chocs inverses": scenario_by_name.get("Hypothese inverse"),
        })
        st.subheader("Evolution du cours et estimation")
        st.line_chart(pd.DataFrame(chart_rows).set_index("Date"))
        st.caption(
            f"Cours observe et estimation a {wheat_prediction.horizon_mois} mois. "
            "Les bornes representent une fourchette basee sur les erreurs passees "
            f"des {wheat_prediction.observations_selection} origines de selection. "
            "Le prix de reference international ne comprend pas les couts de livraison en Tunisie."
        )
        st.info(
            "Le taux de change, les stocks de l'Etat, les contrats d'achat et les couts de "
            "transport ne sont pas integres automatiquement. Utilisez le plan d'approvisionnement "
            "ci-dessous et les donnees fournies par les services concernes."
        )

    st.subheader("Besoin indicatif de provisionnement")
    planning_inputs = (current_stocks, scheduled_arrivals, expected_harvest)
    if provisioning_baseline is None:
        st.warning("Le bilan FAOSTAT est indisponible; le besoin ne peut pas etre estime.")
    elif any(value is None for value in planning_inputs):
        st.info(
            "Renseignez les stocks utilisables, les arrivages contractes et la recolte "
            "attendue pour calculer la quantite a provisionner."
        )
    else:
        plan = calculate_provisioning_plan(
            baseline=provisioning_baseline,
            planning_months=planning_months,
            buffer_days=buffer_days,
            current_stocks_tonnes=current_stocks,
            scheduled_arrivals_tonnes=scheduled_arrivals,
            expected_harvest_tonnes=expected_harvest,
        )
        demand_col, cover_col, procure_col = st.columns(3)
        demand_col.metric(
            "Demande + tampon a couvrir",
            f"{plan.demand_over_horizon_tonnes + plan.target_buffer_tonnes:,.0f} t",
        )
        cover_col.metric("Couverture des stocks actuels", f"{plan.stock_cover_days:,.0f} jours")
        procure_col.metric("Quantite minimale a acheter", f"{plan.quantity_to_procure_tonnes:,.0f} t")
        st.caption(
            f"Calcul base sur la consommation interieure annuelle FAOSTAT {plan.reference_year}, "
            f"les stocks/arrivages/recoltes saisis et un tampon de {plan.buffer_days} jours. "
            "A valider avec le plan de securite alimentaire de l'Etat."
        )

        if wheat_scenario_rows:
            cost_rows = []
            premium = landed_premium_pct or 0.0
            for scenario in wheat_scenario_rows:
                unit_price = scenario["Prix estime (USD/tonne)"] * (1 + premium / 100)
                row = {
                    "Cas": scenario["Cas"],
                    "Cout indicatif (USD)": plan.quantity_to_procure_tonnes * unit_price,
                }
                if usd_tnd is not None:
                    row["Cout indicatif (TND)"] = row["Cout indicatif (USD)"] * usd_tnd
                cost_rows.append(row)
            st.dataframe(pd.DataFrame(cost_rows), hide_index=True, use_container_width=True)
            st.caption(
                "Le cout en TND n'est affiche qu'avec un taux USD/TND renseigne. "
                "La prime fret/assurance/qualite est une hypothese utilisateur, pas une cotation."
            )

