import os

import streamlit as st
from src.agents.explainer_orchestrator_agent.agent import (
    run_gasoil_forecast,
    run_gasoil_simulation,
)

st.title("Prevision du prix du gasoil")
st.caption("Prevision du prix international de l'ULSD et explication des facteurs")

dataset_path = st.text_input(
    "Fichier de donnees CSV",
    value=os.environ.get(
        "GASOIL_FORECAST_DATASET",
        r"E:\Downloads\gasoil_forecasting_dataset.csv",
    ),
)
left, right = st.columns(2)
with left:
    brent_shock_pct = st.number_input("Variation du Brent (%)", 0.0, 100.0, 10.0, 1.0)
with right:
    spread_shock_pct = st.number_input("Variation du crack spread (%)", 0.0, 100.0, 15.0, 1.0)

try:
    forecast = run_gasoil_forecast(
        dataset_path,
        brent_shock_pct=brent_shock_pct,
        crack_spread_shock_pct=spread_shock_pct,
    )
    st.subheader("Scenarios prevus")
    st.caption(
        f"Derniere observation : {forecast.date_derniere_observation} | "
        f"Mois predit : {forecast.date_prevision} | "
        f"Dernier prix observe : ${forecast.dernier_prix_ulsd_usd_gal:.3f}/gallon"
    )
    st.warning(forecast.avertissement)

    scenario_columns = st.columns(len(forecast.scenarios))
    for column, scenario in zip(scenario_columns, forecast.scenarios):
        with column:
            st.metric(
                scenario.nom,
                f"${scenario.prix_ulsd_usd_gal:.3f}/gallon",
                f"{scenario.variation_vs_dernier_pct:+.1f}%",
            )
            st.markdown("**Pourquoi ce prix ?**")
            st.write(scenario.explication)
            st.caption(
                f"Brent : {scenario.brent_usd_bbl:.2f} USD/baril | "
                f"Crack spread : {scenario.crack_spread_usd_bbl:.2f} USD/baril"
            )

    st.subheader("Comment lire la prevision")
    st.write(forecast.methode)
except (OSError, ValueError) as error:
    st.error(f"Impossible de calculer la prevision : {error}")

st.divider()
st.subheader("Simulation « Et si...? »")
st.write("Change les facteurs par rapport au scenario central pour tester une hypothese.")
with st.form("gasoil_what_if_form"):
    brent_column, spread_column = st.columns(2)
    with brent_column:
        simulated_brent_change = st.number_input(
            "Si le Brent varie de (%)", -100.0, 100.0, 0.0, 1.0
        )
    with spread_column:
        simulated_spread_change = st.number_input(
            "Si le crack spread varie de (%)", -100.0, 100.0, 0.0, 1.0
        )
    simulate = st.form_submit_button("Simuler ce scenario", type="primary")

if simulate:
    try:
        simulation = run_gasoil_simulation(
            dataset_path,
            brent_change_pct=simulated_brent_change,
            crack_spread_change_pct=simulated_spread_change,
        )
        st.metric(
            "Prix simule",
            f"${simulation.prix_ulsd_usd_gal:.3f}/gallon",
            f"{simulation.variation_vs_dernier_pct:+.1f}% vs dernier prix observe",
        )
        st.markdown("**Explication de la simulation**")
        st.write(simulation.explication)
        st.caption(
            f"Brent simule : {simulation.brent_usd_bbl:.2f} USD/baril | "
            f"Crack spread simule : {simulation.crack_spread_usd_bbl:.2f} USD/baril"
        )
    except (OSError, ValueError) as error:
        st.error(f"Impossible de calculer la simulation : {error}")
