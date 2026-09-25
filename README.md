# Boussole Budgetaire

Systeme d alerte precoce sur les tendances de prix des matieres
premieres subventionnees, via un pipeline multi-agents hierarchique
(LangGraph).

## Architecture des agents

- **Agent Collecteur** (parent)
  - Sous-agents Variables : prix_international, brent, usd_tnd, inflation
  - Sous-agents Matieres Premieres : ble, petrole (codes) ; plastiques, aluminium (stubs)
- **Agent Meteo/News**
- **Agent Feature Engineer + Predicteur** (fusionne)
- **Agent Explicateur + Orchestration LangGraph** (fusionne, referent contrat)

Voir `src/agents/*/AGENT_CARD.md` (et les AGENT_CARD.md des sous-dossiers
`variables/` et `matieres_premieres/`) pour le role, input/output,
sources et responsable de chaque agent.

## Contrat de donnees
Voir `src/schemas.py`. Referent : Agent Explicateur/Orchestration.

## Lancer
    .\venv\Scripts\Activate.ps1
    python -m src.graph
    streamlit run src/dashboard/app.py
