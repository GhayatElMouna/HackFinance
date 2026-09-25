import streamlit as st
from src.graph import run_pipeline

st.title("Boussole Budgetaire")
matieres = st.multiselect("Matieres premieres", ["ble", "petrole", "plastiques", "aluminium"], default=["ble", "petrole"])
if st.button("Lancer le pipeline"):
    result = run_pipeline(matieres, "zones cerealieres nord Tunisie")
    st.subheader("Predictions")
    st.write(result.feature_predictor.predictions)
    st.subheader("Explications")
    st.write(result.explanations)
