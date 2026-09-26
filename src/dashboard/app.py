import streamlit as st
import pandas as pd
from src.agents.collector_agent.matieres_premieres import cuivre_agent
from src.agents.feature_predictor_agent.agent import forecast_copper_prices

st.title("Cours et previsions du cuivre")
st.caption("Cuivre HS 74 | Prix de reference estime en TND/kg")
horizon_months = st.slider("Horizon de prevision (mois)", min_value=1, max_value=12, value=6)

copper = cuivre_agent.run()
forecast = forecast_copper_prices(copper, horizon_months)
history_dates = pd.to_datetime([point.date for point in copper.points])
history_prices = [point.prix_unitaire for point in copper.points]
forecast_dates = pd.DatetimeIndex(pd.to_datetime(forecast["date"]))
last_date = history_dates[-1]
last_price = history_prices[-1]

chart = pd.DataFrame(
    index=history_dates.append(forecast_dates),
    columns=["Historique", "Prevision"],
    dtype=float,
)
chart.loc[history_dates, "Historique"] = history_prices
chart.loc[last_date, "Prevision"] = last_price
chart.loc[forecast_dates, "Prevision"] = forecast["prix_prevu_tnd_kg"].to_numpy()

final_price = float(forecast["prix_prevu_tnd_kg"].iloc[-1])
change_percent = (final_price / last_price - 1) * 100
latest_metric, forecast_metric, change_metric = st.columns(3)
latest_metric.metric("Dernier prix observe", f"{last_price:.2f} TND/kg")
forecast_metric.metric(
    f"Prevision a {horizon_months} mois",
    f"{final_price:.2f} TND/kg",
)
change_metric.metric("Variation projetee", f"{change_percent:+.1f}%")

st.subheader("Historique et prevision")
st.line_chart(chart, y_label="TND/kg")
st.caption(
    f"{copper.source}. Projection par regression lineaire; "
    "les bornes sont indicatives et ne constituent pas une garantie."
)
st.dataframe(
    forecast.rename(columns={
        "date": "Date",
        "prix_prevu_tnd_kg": "Prix prevu (TND/kg)",
        "borne_basse_indicative": "Borne basse indicative",
        "borne_haute_indicative": "Borne haute indicative",
    }),
    width="stretch",
)

with st.expander("Voir les prix historiques"):
    st.dataframe(
        pd.DataFrame({
            "Date": [point.date for point in copper.points],
            "Prix historique (TND/kg)": history_prices,
        }),
        width="stretch",
    )
