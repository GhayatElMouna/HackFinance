# Boussole Budgetaire

Systeme d alerte precoce sur les tendances de prix des matieres
premieres subventionnees, via un pipeline multi-agents hierarchique
(LangGraph).

## Architecture des agents

- **Agent Collecteur** (parent)
  - Sous-agents Variables : prix_international, brent, usd_tnd, inflation
  - Sous-agents Matieres Premieres : ble, petrole (codes) ; plastiques, aluminium (stubs) ; **fer_acier** (World Bank Iron ore)
- **Agent Meteo/News**
- **Agent Feature Engineer + Predicteur** (fusionne) — SARIMAX sur `fer_acier`
- **Agent Explicateur + Orchestration LangGraph** (fusionne, referent contrat)

Voir `src/agents/*/AGENT_CARD.md` (et les AGENT_CARD.md des sous-dossiers
`variables/` et `matieres_premieres/`) pour le role, input/output,
sources et responsable de chaque agent.

## Contrat de donnees
Voir `src/schemas.py`. Referent : Agent Explicateur/Orchestration.

## Donnees fer/acier
Cache local dans `data/raw/` (`iron_ore_monthly.csv`, `brent_monthly.csv`, etc.).
- World Bank Pink Sheet (commodites)
- FRED : `usd_index_monthly.csv` (indice dollar), `vix_risk_monthly.csv` (risque geo / VIX)
Refresh live optionnel : `REFRESH_WORLDBANK=1` (WB) ; les series FRED se rafraichissent si le cache manque.
Facteurs exogenes selectionnables dans le dashboard Streamlit.

## Lancer
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    python -m src.graph
    streamlit run src/dashboard/app.py
