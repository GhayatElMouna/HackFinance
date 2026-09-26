"""
Dashboard Streamlit — Boussole Budgetaire / TrendGov
Resultats, indicateurs budgetaires et rapport PDF.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from src.dashboard.report_pdf import build_pdf_report
from src.graph import run_pipeline
from src.schemas import PipelineResult

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
LOIS_DIR = ROOT / "data" / "lois_finances"

st.set_page_config(
    page_title="Boussole Budgetaire",
    page_icon="◇",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap');

:root {
  --ink: #1a2332;
  --muted: #5c6b7a;
  --accent: #0f6e56;
  --accent-soft: #d8f3e7;
}

html, body, [class*="css"] {
  font-family: 'DM Sans', sans-serif;
  color: var(--ink);
}

.block-container { padding-top: 1.5rem; max-width: 1100px; }

h1, h2, h3 {
  font-family: 'Fraunces', Georgia, serif !important;
  letter-spacing: -0.02em;
}

.hero {
  background: linear-gradient(135deg, #0f6e56 0%, #1a3a4a 55%, #1a2332 100%);
  color: #f7f4ef;
  border-radius: 18px;
  padding: 1.6rem 1.8rem;
  margin-bottom: 1.2rem;
  box-shadow: 0 12px 40px rgba(26, 35, 50, 0.18);
}
.hero h1 { color: #fff !important; margin: 0 0 0.35rem 0; font-size: 2rem; }
.hero p { margin: 0; opacity: 0.88; font-size: 1.02rem; }

.metric-card {
  background: linear-gradient(180deg, #ffffff 0%, #f7f4ef 100%);
  border: 1px solid #e7e2d9;
  border-radius: 14px;
  padding: 1rem;
}
</style>
""",
    unsafe_allow_html=True,
)

FEATURE_LABELS = {
    "depense_budget_mdt": "Depense budget (MDT)",
    "variation_budget_pct": "Variation (%)",
    "variation_budget_3ans_pct": "Variation 3 ans (%)",
    "score_pression_budgetaire": "Pression budgetaire (0-1)",
    "total_subventions_mdt_latest": "Total subventions (MDT)",
}


def _label_feature(key: str) -> tuple[str, str]:
    for prefix, label in FEATURE_LABELS.items():
        if key == prefix or key.startswith(prefix + "_"):
            matiere = key[len(prefix) :].lstrip("_") or "—"
            return label, matiere.replace("_", " ")
    return key.replace("_", " "), "—"


def features_budget_table(features: dict[str, float]) -> pd.DataFrame:
    rows = []
    for key, value in features.items():
        label, matiere = _label_feature(key)
        rows.append({"Indicateur": label, "Matiere": matiere, "Valeur": value})
    return pd.DataFrame(rows)


def render_results(result: PipelineResult) -> None:
    preds = result.feature_predictor.predictions
    if not preds:
        st.info("Aucune prediction disponible (historique insuffisant ou erreur de collecte).")
    else:
        cols = st.columns(min(3, len(preds)))
        for index, prediction in enumerate(preds):
            with cols[index % len(cols)]:
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.metric(
                    prediction.matiere.capitalize(),
                    prediction.tendance.replace("_", " ").title(),
                    f"confiance {prediction.confiance * 100:.1f}%",
                )
                if prediction.budget_a_influence:
                    st.caption("Facteur budgetaire: influence detectee")
                st.markdown("</div>", unsafe_allow_html=True)

    st.subheader("Feature importance")
    for explanation in result.explanations:
        if not explanation.feature_importances:
            continue
        frame = pd.DataFrame(
            [
                {"Facteur": key.replace("_", " "), "Poids %": value}
                for key, value in explanation.feature_importances.items()
            ]
        )
        colors = [
            "#0f6e56"
            if "budget" in row["Facteur"].lower() or "depense" in row["Facteur"].lower()
            else "#64748b"
            for _, row in frame.iterrows()
        ]
        fig = go.Figure(
            go.Bar(
                x=frame["Poids %"],
                y=frame["Facteur"],
                orientation="h",
                marker_color=colors,
                text=[f"{v:.1f}%" for v in frame["Poids %"]],
                textposition="outside",
            )
        )
        fig.update_layout(
            title=f"{explanation.matiere.capitalize()} — poids indicatifs",
            height=260,
            margin=dict(l=10, r=40, t=50, b=10),
            xaxis_title="Poids (%)",
            yaxis_title="",
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
            key=f"importance_{explanation.matiere}",
        )
        st.write(explanation.texte_explicatif)
        if explanation.budget_mentionne:
            st.success("Le facteur depenses budgetaires est explicitement pris en compte.")

    if result.lois_finances:
        st.subheader("Lois de Finances (2024–2026)")
        st.caption(
            f"Mode: {result.lois_finances.source_mode} · "
            f"Annees: {', '.join(map(str, result.lois_finances.annees_analysees))}"
        )
        for warning in result.lois_finances.warnings:
            st.warning(warning)

        rows = []
        for year_summary in result.lois_finances.resumes_par_annee:
            for line in year_summary.lignes:
                rows.append(
                    {
                        "Annee": line.annee,
                        "Poste": line.poste,
                        "Matiere": line.matiere or "—",
                        "Montant MDT": line.montant_mdt,
                        "Variation %": line.variation_pct,
                    }
                )
        if rows:
            budget_df = pd.DataFrame(rows)
            fig = px.bar(
                budget_df,
                x="Annee",
                y="Montant MDT",
                color="Matiere",
                barmode="group",
                title="Depenses / subventions par matiere (MDT)",
                color_discrete_sequence=["#0f6e56", "#1d4ed8", "#b45309", "#64748b"],
            )
            fig.update_layout(height=360, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True, key="budget_bar_lois")
            st.dataframe(budget_df, use_container_width=True, hide_index=True)

        features = result.lois_finances.features_budgetaires or {}
        if features:
            st.markdown("##### Indicateurs budgetaires derives")
            feat_df = features_budget_table(features)
            st.dataframe(feat_df, use_container_width=True, hide_index=True)
            chart_df = feat_df[
                feat_df["Indicateur"].isin(
                    [
                        "Depense budget (MDT)",
                        "Variation (%)",
                        "Variation 3 ans (%)",
                        "Pression budgetaire (0-1)",
                        "Total subventions (MDT)",
                    ]
                )
            ]
            if not chart_df.empty:
                fig_feat = px.bar(
                    chart_df,
                    x="Indicateur",
                    y="Valeur",
                    color="Matiere",
                    barmode="group",
                    title="Synthese des features budgetaires",
                    color_discrete_sequence=["#0f6e56", "#1d4ed8", "#b45309"],
                )
                fig_feat.update_layout(height=320, margin=dict(l=10, r=10, t=50, b=10))
                st.plotly_chart(fig_feat, use_container_width=True, key="features_budget_chart")

    st.subheader("Meteo & actualites")
    st.caption(f"Source: {result.weather_news.source} · Zone: {result.weather_news.zone}")
    st.metric("Score de risque agrege", f"{result.weather_news.score_risque:.2f}")
    if result.weather_news.collection_errors:
        for err in result.weather_news.collection_errors:
            st.warning(err)
    if result.weather_news.events:
        news_df = pd.DataFrame(
            [
                {
                    "Date": event.date.isoformat(),
                    "Impact": event.score_impact,
                    "Titre": event.titre,
                }
                for event in result.weather_news.events
            ]
        )
        st.dataframe(news_df, use_container_width=True, hide_index=True)
    else:
        st.info("Aucun evenement meteo/news pour cette execution.")

    with st.expander("Donnees collectees"):
        if result.collector.collection_errors:
            for err in result.collector.collection_errors:
                st.warning(err)
        latest = [
            {
                "Serie": variable.nom,
                "Date": variable.date.isoformat(),
                "Valeur": variable.valeur,
                "Unite": variable.unite,
                "Source": variable.source,
            }
            for variable in result.collector.variables
        ]
        for material in result.collector.matieres_premieres:
            if not material.points:
                continue
            point = material.points[-1]
            latest.append(
                {
                    "Serie": material.matiere,
                    "Date": point.date.isoformat(),
                    "Valeur": point.prix_unitaire,
                    "Unite": material.source,
                    "Source": material.source,
                }
            )
        if latest:
            st.dataframe(latest, use_container_width=True, hide_index=True)


# ---------- UI ----------
st.markdown(
    """
<div class="hero">
  <h1>Boussole Budgetaire</h1>
  <p>Detection precoce de tendances de prix — pipeline multi-agents
  (Variables · Matieres premieres · Lois de Finances · News · Prediction).</p>
</div>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Parametres")
    matieres = st.multiselect(
        "Matieres premieres",
        ["petrole", "ble", "aluminium", "cuivre", "fer_acier", "plastiques"],
        default=["petrole"],
    )
    zone = st.text_input("Zone meteo", "zones cerealieres nord Tunisie")
    horizon = st.select_slider("Horizon (mois)", options=[1, 3, 6, 9, 12], value=3)
    st.markdown("---")
    st.subheader("Lois de Finances")
    st.caption("Deposez les PDF dans le dossier du projet :")
    st.code("data/lois_finances/\n  lf_2024.pdf\n  lf_2025.pdf\n  lf_2026.pdf", language=None)
    existing = sorted(p.name for p in LOIS_DIR.glob("lf_*.pdf")) if LOIS_DIR.exists() else []
    if existing:
        st.success("PDF detectes: " + ", ".join(existing))
    else:
        st.info("Aucun PDF detecte — extraits curated utilises.")
    st.markdown("---")
    st.subheader("NewsAPI / Gemini")
    st.caption(
        "Cles dans `.env` : `NEWS_API_KEY`, `GEMINI_API_KEY` "
        "(scoring LLM des actualites + enrichissement Lois de Finances)."
    )
    run_clicked = st.button("Lancer le pipeline", type="primary", use_container_width=True)

if "pipeline_result" not in st.session_state:
    st.session_state.pipeline_result = None

if run_clicked:
    if not matieres:
        st.error("Selectionnez au moins une matiere.")
    else:
        with st.spinner("Pipeline en cours…"):
            try:
                result = run_pipeline(matieres, zone, horizon_mois=horizon)
                st.session_state.pipeline_result = result
                st.success("Pipeline termine.")
            except Exception as error:
                st.error(str(error))

if st.session_state.pipeline_result is not None:
    st.subheader("Resultats")
    render_results(st.session_state.pipeline_result)

    st.subheader("Rapport PDF")
    try:
        pdf_bytes = build_pdf_report(st.session_state.pipeline_result)
        st.download_button(
            "Telecharger le rapport PDF",
            data=pdf_bytes,
            file_name="boussole_budgetaire_rapport.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )
    except Exception as error:
        st.error(f"Generation PDF impossible: {error}")
