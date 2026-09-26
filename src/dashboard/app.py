import pandas as pd
import streamlit as st
import altair as alt
from src.graph import run_pipeline
from src.agents.collector_agent.matieres_premieres.aluminium_agent import run as collect_aluminium
from src.agents.feature_predictor_agent.agent import forecast_monthly_price
from src.schemas import ProvisioningRequest
from src.agents.provisioning_agent.agent import (
    run as run_provisioning,
    run_with_web_price,
)

st.title("Boussole Budgetaire")
st.caption("Sources web officielles, prevision de prix et recommandations de stock.")
matieres = st.multiselect(
    "Matieres premieres",
    ["ble", "petrole", "plastiques", "aluminium"],
    default=["ble", "petrole", "aluminium"],
)

with st.expander("Agent de provisionnement aluminium", expanded=True):
    st.caption("Recommandation de stock uniquement; aucune commande n'est envoyee.")
    st.info("Valeurs pre-remplies illustratives: remplace-les par les donnees de stock reelles.")
    with st.form("provisioning_form"):
        stock_col, demand_col, transit_col = st.columns(3)
        stock = stock_col.number_input(
            "Stock disponible (t)", min_value=0.0, value=25.0, step=1.0
        )
        daily_demand = demand_col.number_input(
            "Consommation moyenne (t/jour)", min_value=0.01, value=1.2, step=0.1
        )
        in_transit = transit_col.number_input(
            "Stock en transit (t)", min_value=0.0, value=0.0, step=1.0
        )
        lead_col, safety_col, price_col = st.columns(3)
        lead_days = lead_col.number_input(
            "Delai fournisseur (jours)", min_value=0, value=21, step=1
        )
        safety_days = safety_col.number_input(
            "Stock de securite (jours)", min_value=0, value=14, step=1
        )
        unit_price = price_col.number_input(
            "Prix achat (TND/t, optionnel)", min_value=0.0, value=0.0, step=100.0
        )
        st.caption("Laisser le prix a 0 pour utiliser le benchmark web aluminium converti en TND.")
        provisioning_clicked = st.form_submit_button("Calculer le provisionnement")

    if provisioning_clicked:
        provisioning_request = ProvisioningRequest(
            matiere="aluminium",
            stock_disponible_t=stock,
            consommation_journaliere_t=daily_demand,
            delai_approvisionnement_jours=lead_days,
            stock_securite_jours=safety_days,
            quantite_en_transit_t=in_transit,
            prix_unitaire_tnd_t=unit_price or None,
        )
        if unit_price > 0:
            recommendation = run_provisioning(provisioning_request)
        else:
            try:
                recommendation = run_with_web_price(provisioning_request)
            except Exception as error:
                recommendation = run_provisioning(provisioning_request)
                st.warning(
                    f"Prix web indisponible ({error}); recommandation calculee sans estimation du cout."
                )
        coverage_col, quantity_col, status_col = st.columns(3)
        coverage_col.metric("Couverture estimee", f"{recommendation.couverture_jours:.1f} jours")
        quantity_col.metric("Quantite a commander", f"{recommendation.quantite_a_commander_t:.3f} t")
        status_col.metric("Niveau", recommendation.niveau_urgence.replace("_", " ").title())
        if recommendation.date_commande_recommandee:
            st.write(f"Date conseillee: {recommendation.date_commande_recommandee.isoformat()}")
        st.write(recommendation.justification)
        if recommendation.cout_estime_tnd is not None:
            st.metric("Cout indicatif", f"{recommendation.cout_estime_tnd:,.3f} TND")
            if recommendation.source_prix:
                st.caption(
                    f"Prix de reference: {recommendation.source_prix}"
                    + (f", observation du {recommendation.date_prix.isoformat()}" if recommendation.date_prix else "")
                )

forecast_horizon = st.select_slider(
    "Horizon de prevision aluminium (mois)",
    options=[1, 3, 6, 9, 12],
    value=6,
)
forecast_clicked = st.button(
    "Prevoir le prix futur depuis FRED", type="primary"
)
pipeline_clicked = st.button("Lancer le pipeline avec les sources disponibles")

if forecast_clicked:
    try:
        aluminium = collect_aluminium()
        forecast = forecast_monthly_price(aluminium, forecast_horizon)
    except Exception as error:
        st.error(f"Prevision indisponible: {error}")
    else:
        st.subheader("Prevision mensuelle aluminium")
        st.caption(
            f"Source: {forecast.source}. Derniere observation: "
            f"{forecast.derniere_observation.isoformat()}. Unite: {forecast.unite}."
        )
        observed_col, mae_col, mape_col = st.columns(3)
        observed_col.metric(
            "Dernier prix observe", f"{forecast.dernier_prix:,.2f} {forecast.unite}"
        )
        mae_col.metric(
            f"Erreur MAE (test final, {forecast.observations_validation} mois)",
            f"{forecast.erreur_absolue_validation:,.2f} {forecast.unite}",
        )
        mape_col.metric(
            "Erreur MAPE sur test final",
            f"{forecast.erreur_relative_validation_pct:.2f}%",
        )
        st.caption(
            f"Methode retenue sur les 12 mois precedents: {forecast.methode.replace('_', ' ')}. "
            "La plage affiche l'erreur historique empirique, pas un intervalle de confiance."
        )
        forecast_rows = [point.model_dump() for point in forecast.previsions]
        forecast_table = pd.DataFrame(forecast_rows).rename(
            columns={
                "date": "Mois",
                "prix_prevu": "Prix prevu",
                "borne_basse": "Borne basse empirique",
                "borne_haute": "Borne haute empirique",
            }
        )
        st.dataframe(forecast_table, use_container_width=True, hide_index=True)

        history_rows = [
            {"Date": point.date, "Prix": point.prix_unitaire, "Serie": "Historique"}
            for point in aluminium.points[-36:]
        ]
        forecast_rows = [
            {
                "Date": forecast.derniere_observation,
                "Prix": forecast.dernier_prix,
                "Serie": "Prevision",
            }
        ]
        forecast_rows.extend(
            {"Date": point.date, "Prix": point.prix_prevu, "Serie": "Prevision"}
            for point in forecast.previsions
        )
        chart_data = pd.DataFrame(history_rows + forecast_rows)
        chart = (
            alt.Chart(chart_data)
            .mark_line(point=True)
            .encode(
                x=alt.X("Date:T", title="Mois"),
                y=alt.Y("Prix:Q", title=f"Prix ({forecast.unite})"),
                color=alt.Color("Serie:N", title="Serie"),
                tooltip=["Date:T", "Serie:N", alt.Tooltip("Prix:Q", format=",.2f")],
            )
        )
        st.altair_chart(chart, width="stretch")
        st.warning(
            "C'est une prevision de reference basee sur l'historique, pas une garantie. "
            "Elle prevoit un prix constant lorsque le dernier prix est le meilleur modele au backtest."
        )

if pipeline_clicked:
    result = run_pipeline(matieres, "zones cerealieres nord Tunisie")
    for collection_error in result.collector.collection_errors:
        st.warning(f"Collecte web: {collection_error}")
    for collection_error in result.weather_news.collection_errors:
        st.warning(f"Meteo web: {collection_error}")
    st.caption(f"Meteo: {result.weather_news.source}")
    st.subheader("Dernieres donnees web")
    latest_data = [
        {
            "Type": "Variable",
            "Serie": variable.nom,
            "Date": variable.date.isoformat(),
            "Valeur": variable.valeur,
            "Unite": variable.unite,
            "Source": variable.source,
        }
        for variable in result.collector.variables
    ]
    latest_data.extend(
        {
            "Type": material.points[-1].type_donnee,
            "Serie": material.matiere,
            "Date": material.points[-1].date.isoformat(),
            "Valeur": material.points[-1].prix_unitaire,
            "Unite": material.source,
            "Source": material.source,
        }
        for material in result.collector.matieres_premieres
        if material.points
    )
    if latest_data:
        st.dataframe(latest_data, use_container_width=True, hide_index=True)
        st.caption(
            "Les prix matieres affiches sont des benchmarks internationaux; "
            "ils ne representent pas les quantites/prix d'importation tunisiennes."
        )
    else:
        st.info("Aucune donnee web n'a ete collectee.")
    st.subheader("Predictions")
    if result.feature_predictor.predictions:
        st.dataframe(
            [
                {"Matiere": prediction.matiere, "Direction recente": prediction.tendance}
                for prediction in result.feature_predictor.predictions
            ],
            use_container_width=True,
            hide_index=True,
        )
        st.caption("Cette direction resume l'historique disponible; ce n'est pas une prevision de prix futur.")
    else:
        st.info(
            "Aucune prediction: il faut au moins deux observations reelles pour une matiere."
        )
    st.subheader("Explications")
    if result.explanations:
        for explanation in result.explanations:
            st.markdown(f"**{explanation.matiere.capitalize()}**")
            st.write(explanation.texte_explicatif)
            if explanation.feature_importances:
                momentum_weight = explanation.feature_importances.get(
                    "momentum_prix_indicatif_pct", 0.0
                )
                volatility_weight = explanation.feature_importances.get(
                    "volatilite_indicative_pct", 0.0
                )
                st.caption(
                    "Poids indicatifs (pas SHAP): "
                    f"momentum {momentum_weight:.1f}% · "
                    f"volatilite {volatility_weight:.1f}%"
                )
    else:
        st.info("Aucune explication disponible pour ce resultat.")
