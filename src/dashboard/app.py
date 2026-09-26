import sys
from pathlib import Path

# Racine du projet sur PYTHONPATH pour `streamlit run`
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import importlib

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from src.data.worldbank_prices import FACTOR_CATALOG, factor_options_fr

try:
    from src.data.worldbank_prices import DEFAULT_FACTORS
except ImportError:
    DEFAULT_FACTORS = ["brent", "charbon", "cuivre", "aluminium"]


def _run_pipeline(**kwargs):
    """Recharge les modules agents/graph (evite le cache Streamlit stale)."""
    import src.data.worldbank_prices as wb
    import src.agents.feature_predictor_agent.agent as fp_agent
    import src.agents.explainer_orchestrator_agent.agent as exp_agent
    import src.agents.collector_agent.agent as col_agent
    import src.agents.weather_news_agent.agent as wn_agent
    import src.agents.collector_agent.matieres_premieres.fer_acier_agent as fer_agent
    import src.graph as graph_mod

    importlib.reload(wb)
    importlib.reload(fer_agent)
    importlib.reload(col_agent)
    importlib.reload(wn_agent)
    importlib.reload(fp_agent)
    importlib.reload(exp_agent)
    importlib.reload(graph_mod)
    return graph_mod.run_pipeline(**kwargs)

TENDANCE_FR = {
    "hausse": "Hausse",
    "baisse": "Baisse",
    "stable_volatile": "Stable / volatile",
}

ATTR_BASE = {
    "prix_actuel_usd": "Prix actuel (USD/t)",
    "moyenne_3m": "Moyenne 3 mois",
    "moyenne_12m": "Moyenne 12 mois",
    "momentum_3m_pct": "Momentum 3 mois (%)",
    "momentum_12m_pct": "Momentum 12 mois (%)",
    "volatilite_6m_pct": "Volatilité 6 mois (%)",
    "variation_prevue_pct": "Variation prévue (%)",
    "ecart_vs_moyenne_12m_pct": "Écart vs moyenne 12m (%)",
    "horizon_mois": "Horizon (mois)",
}

# Labels dynamiques pour chaque facteur catalogue
ATTR_LABELS = dict(ATTR_BASE)
for key, meta in FACTOR_CATALOG.items():
    ATTR_LABELS[f"exog_{key}"] = meta["label_fr"]
    ATTR_LABELS[f"exog_{key}_var_3m_pct"] = f"{meta['label_fr']} var. 3m (%)"

st.set_page_config(page_title="Boussole Budgétaire — Fer / Acier", layout="wide")
st.title("Boussole Budgétaire — Fer / Acier")
st.caption(
    "Alerte précoce sur les prix mondiaux du fer/acier "
    "(proxy minerai de fer, Banque mondiale) — prévision SARIMAX"
)

horizon = st.slider("Horizon de prévision (mois)", min_value=1, max_value=12, value=3)
annee_debut = st.slider(
    "Année de début de l'historique",
    min_value=2010,
    max_value=2022,
    value=2015,
    help="Le modèle n'utilise que les données à partir de cette année. "
    "Une fenêtre plus courte réagit mieux aux tendances récentes.",
)

options = factor_options_fr()
facteurs = st.multiselect(
    "Facteurs exogènes (cocher / décocher)",
    options=list(options.keys()),
    default=[k for k in DEFAULT_FACTORS if k in options],
    format_func=lambda k: options.get(k, k),
    help="Ces séries World Bank entrent dans le SARIMAX. Aucun facteur = SARIMA pur.",
)
st.caption(
    f"{len(facteurs)} facteur(s) sélectionné(s). "
    "Maximum recommandé : 5 (stabilité du modèle)."
)

if st.button("Lancer l'analyse", type="primary"):
    with st.spinner("Collecte des données et calcul SARIMAX…"):
        result = _run_pipeline(
            matieres=["fer_acier"],
            horizon=horizon,
            facteurs=facteurs,
            annee_debut=annee_debut,
        )

    pred = next(
        (p for p in result.feature_predictor.predictions if p.matiere == "fer_acier"),
        None,
    )
    if pred is None:
        st.error("Aucune prédiction fer/acier disponible.")
        st.stop()

    st.subheader("Prévision")
    cols = st.columns(4)
    cols[0].metric("Matière", "Fer / acier")
    cols[1].metric("Tendance", TENDANCE_FR.get(pred.tendance, pred.tendance))
    cols[2].metric("Confiance", f"{pred.confiance:.0%}")
    variation = getattr(pred, "variation_prevue_pct", None)
    if variation is None and isinstance(getattr(pred, "attributs", None), dict):
        variation = pred.attributs.get("variation_prevue_pct", 0.0)
    cols[3].metric("Variation prévue", f"{float(variation or 0.0):+.2f} %")
    st.caption(
        f"Modèle : {pred.modele.upper()} — facteurs : "
        + (", ".join(options[k] for k in facteurs) if facteurs else "aucun (SARIMA)")
    )

    st.subheader("Attributs")
    attrs = getattr(pred, "attributs", None) or {}
    if not attrs:
        st.info("Aucun attribut renvoyé. Relancez via `streamlit run run_dashboard.py`.")
    display_keys = [k for k in ATTR_LABELS if k in attrs]
    for k in attrs:
        if k.startswith("exog_") and k not in display_keys:
            display_keys.append(k)

    metric_cols = st.columns(4)
    for i, key in enumerate(display_keys):
        label = ATTR_LABELS.get(key, key)
        val = attrs[key]
        text = f"{val:.2f}" if isinstance(val, float) else str(val)
        metric_cols[i % 4].metric(label, text)

    if pred.historique or pred.forecast:
        hist = pd.DataFrame([p.model_dump() for p in pred.historique])
        fc = pd.DataFrame([p.model_dump() for p in pred.forecast])
        if not hist.empty:
            hist["date"] = pd.to_datetime(hist["date"])
        if not fc.empty:
            fc["date"] = pd.to_datetime(fc["date"])

        fig = go.Figure()
        if not hist.empty:
            fig.add_trace(
                go.Scatter(
                    x=hist["date"],
                    y=hist["yhat"],
                    name="Historique",
                    mode="lines",
                    line=dict(color="#1f4e79", width=2),
                )
            )
        if not fc.empty:
            if fc["yhat_upper"].notna().any() and fc["yhat_lower"].notna().any():
                fig.add_trace(
                    go.Scatter(
                        x=fc["date"],
                        y=fc["yhat_upper"],
                        name="Borne haute",
                        mode="lines",
                        line=dict(width=0),
                        showlegend=False,
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=fc["date"],
                        y=fc["yhat_lower"],
                        name="Intervalle de confiance (80 %)",
                        mode="lines",
                        line=dict(width=0),
                        fill="tonexty",
                        fillcolor="rgba(214, 122, 36, 0.25)",
                    )
                )
            fig.add_trace(
                go.Scatter(
                    x=fc["date"],
                    y=fc["yhat"],
                    name="Prévision SARIMAX",
                    mode="lines+markers",
                    line=dict(color="#d67a24", width=2, dash="dash"),
                )
            )
        fig.update_layout(
            title="Prix fer/acier (minerai de fer, Banque mondiale) — historique et prévision",
            xaxis_title="Date",
            yaxis_title="Prix (USD / tonne sèche)",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(l=40, r=20, t=60, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Explication")
    for exp in result.explanations:
        if exp.matiere != "fer_acier":
            continue
        st.write(exp.texte_explicatif)
        if exp.feature_importances:
            labels = {
                "serie_prix_fer": "Série prix du fer",
                "saisonnalite_mensuelle": "Saisonnalité mensuelle",
                **{k: v["label_fr"] for k, v in FACTOR_CATALOG.items()},
            }
            st.write(
                {
                    labels.get(k, k): f"{v:.0%}"
                    for k, v in exp.feature_importances.items()
                }
            )

    with st.expander("Détails de la collecte"):
        for m in result.collector.matieres_premieres:
            if m.matiere != "fer_acier":
                continue
            synth = "oui" if m.is_synthetic else "non"
            st.write(
                f"**Fer / acier** — {len(m.points)} observations mensuelles — "
                f"source : {m.source} — données synthétiques : {synth}"
            )
        st.write(f"Cache données : `data/raw/` — facteurs demandés : {facteurs}")
