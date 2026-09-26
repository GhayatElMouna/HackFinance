"""
Dashboard Streamlit — Boussole Budgetaire / TrendGov
Visualisation du pipeline multi-agents LangGraph et des resultats.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.graph import DEFAULT_STATUS, run_pipeline
from src.schemas import PipelineResult

ROOT = Path(__file__).resolve().parents[2]

st.set_page_config(
    page_title="Boussole Budgetaire",
    page_icon="◇",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Theme CSS ---
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap');

:root {
  --ink: #1a2332;
  --muted: #5c6b7a;
  --surface: #f7f4ef;
  --card: #ffffff;
  --accent: #0f6e56;
  --accent-soft: #d8f3e7;
  --warn: #b45309;
  --err: #b91c1c;
  --idle: #94a3b8;
  --run: #2563eb;
  --done: #0f6e56;
}

html, body, [class*="css"] {
  font-family: 'DM Sans', sans-serif;
  color: var(--ink);
}

.block-container { padding-top: 1.5rem; max-width: 1200px; }

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

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.65rem;
  margin: 0.8rem 0 1.2rem;
}
.status-pill {
  background: var(--card);
  border: 1px solid #e7e2d9;
  border-radius: 12px;
  padding: 0.7rem 0.8rem;
  text-align: center;
}
.status-pill .name { font-size: 0.78rem; color: var(--muted); margin-bottom: 0.25rem; }
.status-pill .badge {
  display: inline-block;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
}
.badge-idle { background: #e2e8f0; color: #475569; }
.badge-running { background: #dbeafe; color: #1d4ed8; }
.badge-done { background: var(--accent-soft); color: var(--accent); }
.badge-error { background: #fee2e2; color: var(--err); }

.graph-box {
  background: var(--card);
  border: 1px solid #e7e2d9;
  border-radius: 14px;
  padding: 1rem 1.1rem;
  margin-bottom: 1rem;
}
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

AGENT_LABELS = {
    "collecteur": "Collecteur",
    "variables": "Variables",
    "matieres_premieres": "Matieres 1eres",
    "lois_finances": "Lois de Finances",
    "weather_news": "Meteo/News",
    "feature_engineer": "Feature Eng.",
    "predicteur": "Predicteur",
    "explicateur": "Explicateur",
}

ORCH_NODES = [
    "collecteur",
    "variables",
    "matieres_premieres",
    "lois_finances",
    "weather_news",
    "feature_engineer",
    "predicteur",
    "explicateur",
]


def _badge_class(status: str) -> str:
    return {
        "idle": "badge-idle",
        "running": "badge-running",
        "done": "badge-done",
        "error": "badge-error",
    }.get(status, "badge-idle")


def render_status(status: dict[str, str]) -> None:
    cells = []
    for key in ORCH_NODES:
        value = status.get(key, "idle")
        cells.append(
            f'<div class="status-pill"><div class="name">{AGENT_LABELS[key]}</div>'
            f'<span class="badge {_badge_class(value)}">{value}</span></div>'
        )
    st.markdown(f'<div class="status-grid">{"".join(cells)}</div>', unsafe_allow_html=True)


def render_orchestration_graph(status: dict[str, str]) -> None:
    color_map = {
        "idle": "#94a3b8",
        "running": "#2563eb",
        "done": "#0f6e56",
        "error": "#b91c1c",
    }
    nodes = [
        ("Collecteur", 0.5, 1.0, "collecteur"),
        ("Variables", 0.12, 0.72, "variables"),
        ("Matieres", 0.38, 0.72, "matieres_premieres"),
        ("Lois Finances", 0.62, 0.72, "lois_finances"),
        ("Meteo/News", 0.88, 0.72, "weather_news"),
        ("Feature Eng.", 0.5, 0.45, "feature_engineer"),
        ("Predicteur", 0.5, 0.25, "predicteur"),
        ("Explicateur", 0.5, 0.08, "explicateur"),
    ]
    edges = [
        (0, 1), (0, 2), (0, 3), (0, 4),
        (1, 5), (2, 5), (3, 5), (4, 5),
        (5, 6), (6, 7),
    ]
    fig = go.Figure()
    for i, j in edges:
        fig.add_trace(
            go.Scatter(
                x=[nodes[i][1], nodes[j][1]],
                y=[nodes[i][2], nodes[j][2]],
                mode="lines",
                line=dict(color="#cbd5e1", width=2),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    fig.add_trace(
        go.Scatter(
            x=[n[1] for n in nodes],
            y=[n[2] for n in nodes],
            mode="markers+text",
            text=[n[0] for n in nodes],
            textposition="top center",
            marker=dict(
                size=28,
                color=[color_map.get(status.get(n[3], "idle"), "#94a3b8") for n in nodes],
                line=dict(width=2, color="white"),
            ),
            hovertext=[f"{n[0]}: {status.get(n[3], 'idle')}" for n in nodes],
            hoverinfo="text",
            showlegend=False,
        )
    )
    fig.update_layout(
        height=340,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(visible=False, range=[-0.05, 1.05]),
        yaxis=dict(visible=False, range=[0, 1.15]),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_results(result: PipelineResult) -> None:
    preds = result.feature_predictor.predictions
    if not preds:
        st.info("Aucune prediction disponible (historique insuffisant ou erreur de collecte).")
        return

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

    # Feature importance charts
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
        # Highlight budget bar
        colors = [
            "#0f6e56" if "budget" in row["Facteur"].lower() or "depense" in row["Facteur"].lower()
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
        st.plotly_chart(fig, use_container_width=True)
        st.write(explanation.texte_explicatif)
        if explanation.budget_mentionne:
            st.success("Le facteur depenses budgetaires est explicitement pris en compte.")

    # Lois de finances panel
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
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(budget_df, use_container_width=True, hide_index=True)

        if result.lois_finances.features_budgetaires:
            st.json(result.lois_finances.features_budgetaires)

    # Collector snapshot
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
  <p>Detection precoce de tendances de prix — pipeline multi-agents LangGraph
  (Variables · Matieres premieres · Lois de Finances · Feature · Prediction · Explication).</p>
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
    st.caption(
        "PDF Lois de Finances: placez `lf_2024.pdf`, `lf_2025.pdf`, `lf_2026.pdf` "
        f"dans `{ROOT / 'data' / 'lois_finances'}`."
    )
    run_clicked = st.button("Lancer le pipeline", type="primary", use_container_width=True)

status_placeholder = st.empty()
graph_placeholder = st.empty()
result_placeholder = st.empty()

if "pipeline_status" not in st.session_state:
    st.session_state.pipeline_status = dict(DEFAULT_STATUS)
if "pipeline_result" not in st.session_state:
    st.session_state.pipeline_result = None

with status_placeholder.container():
    st.subheader("Etat des agents")
    render_status(st.session_state.pipeline_status)

with graph_placeholder.container():
    st.subheader("Graph d'orchestration")
    st.markdown('<div class="graph-box">', unsafe_allow_html=True)
    render_orchestration_graph(st.session_state.pipeline_status)
    st.markdown("</div>", unsafe_allow_html=True)

if run_clicked:
    if not matieres:
        st.error("Selectionnez au moins une matiere.")
    else:
        live_status = dict(DEFAULT_STATUS)
        status_box = st.status("Pipeline en cours…", expanded=True)

        def on_status(updated: dict[str, str]) -> None:
            live_status.update(updated)
            st.session_state.pipeline_status = dict(live_status)
            with status_placeholder.container():
                st.subheader("Etat des agents")
                render_status(live_status)
            with graph_placeholder.container():
                st.subheader("Graph d'orchestration")
                render_orchestration_graph(live_status)
            running = [k for k, v in live_status.items() if v == "running"]
            status_box.write(
                "Agents: "
                + ", ".join(f"{AGENT_LABELS.get(k, k)}={v}" for k, v in live_status.items() if k in ORCH_NODES)
            )
            if running:
                status_box.update(label=f"En cours: {', '.join(AGENT_LABELS.get(r, r) for r in running)}")

        try:
            result = run_pipeline(
                matieres,
                zone,
                horizon_mois=horizon,
                status_callback=on_status,
            )
            st.session_state.pipeline_result = result
            st.session_state.pipeline_status = result.agent_status or live_status
            status_box.update(label="Pipeline termine", state="complete")
        except Exception as error:
            status_box.update(label="Pipeline en erreur", state="error")
            st.error(str(error))

if st.session_state.pipeline_result is not None:
    with result_placeholder.container():
        st.subheader("Resultats")
        render_results(st.session_state.pipeline_result)

    # Export
    with st.expander("Export JSON"):
        payload = st.session_state.pipeline_result.model_dump(mode="json")
        st.download_button(
            "Telecharger le resultat",
            data=json.dumps(payload, ensure_ascii=False, indent=2),
            file_name="boussole_result.json",
            mime="application/json",
        )
