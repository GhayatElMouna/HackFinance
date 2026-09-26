# Boussole Budgetaire / TrendGov

Systeme d'alerte precoce sur les tendances de prix des matieres
premieres subventionnees (Tunisie), via un pipeline multi-agents
hierarchique **LangGraph**.

Objectif : classifier une tendance (**Hausse soutenue / Baisse soutenue /
Stable-volatile**) avec indice de confiance et feature importance —
pas predire un prix exact comme livrable principal.

## Architecture

```
Collecteur (orchestrateur racine)
  ├─ Sous-orchestrateur Variables      (prix_int, brent, usd_tnd, inflation)
  ├─ Sous-orchestrateur Matieres Prem. (ble, petrole, aluminium, cuivre, fer_acier, …)
  ├─ Agent Lois de Finances            (LF 2024–2026, subventions)
  └─ Agent Meteo/News                  (Open-Meteo)
        ↓ merge
  Feature Engineer → Predicteur → Explicateur
```

Les 4 branches amont tournent **en parallele** (StateGraph LangGraph),
puis fusionnent avant le feature engineering.

## Agents

| Agent | Dossier |
|---|---|
| Collecteur + sous-orchestrateurs | `src/agents/collector_agent/` |
| Lois de Finances | `src/agents/lois_finances_agent/` |
| Meteo/News | `src/agents/weather_news_agent/` |
| Feature + Predicteur | `src/agents/feature_predictor_agent/` |
| Explicateur | `src/agents/explainer_orchestrator_agent/` |

Voir `src/agents/*/AGENT_CARD.md` pour le detail input/output.

## Lois de Finances

1. Des extraits structures sont fournis dans
   `data/lois_finances/extraits_curated.json` (demo offline).
2. Placez optionnellement les PDF :
   - `data/lois_finances/lf_2024.pdf`
   - `data/lois_finances/lf_2025.pdf`
   - `data/lois_finances/lf_2026.pdf`
3. Si `OPENAI_API_KEY` (ou `LLM_API_KEY`) est defini, un LLM enrichit
   le resume a partir du texte PDF.

## Lancer (commande unique recommandee)

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.graph
streamlit run run_dashboard.py
```

Configurer `.env` (voir `.env.example`) :

- `NEWS_API_KEY` — cle [NewsAPI](https://newsapi.org/) pour les actualites
- `GEMINI_API_KEY` — cle Google AI Studio / Gemini (scoring news + enrichissement LF)
- `LLM_MODEL` — defaut `gemini-2.5-flash` (`LLM_PROVIDER=gemini`)

Le dashboard propose un **rapport PDF** (plus d'export JSON).

## Contrat de donnees

Voir `src/schemas.py` (`FinanceLawOutput`, `FeatureRow` avec champs budgetaires,
`PipelineResult.agent_status`, etc.).

## Sources web

FRED (aluminium, Brent), Banque mondiale (USD/TND, inflation, Pink Sheet),
Open-Meteo (risque meteo). Les series matieres sont des **benchmarks
internationaux**, pas les prix d'import tunisiens. Les erreurs de sources
sont remontees explicitement.
