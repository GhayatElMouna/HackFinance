# Boussole Budgetaire

Systeme d aide a la decision pour les achats strategiques de ble en Tunisie:
prevision du benchmark international et estimation du besoin de provisionnement.

## Architecture des agents

- **Agent Collecteur** (parent)
  - Sous-agents Variables : prix_international, brent, usd_tnd, inflation
  - Sous-agents Matieres Premieres : ble, petrole (codes) ; plastiques, aluminium (stubs)
- **Agent Meteo/News**
- **Agent Feature Engineer + Predicteur**: selection temporelle, Prophet et scenarios de facteurs
- **Agent Provisionnement**: demande FAOSTAT + stocks, arrivees et recolte saisis
- **Agent Explicateur + Orchestration LangGraph** (fusionne, referent contrat)

Voir `src/agents/*/AGENT_CARD.md` (et les AGENT_CARD.md des sous-dossiers
`variables/` et `matieres_premieres/`) pour le role, input/output,
sources et responsable de chaque agent.

## Contrat de donnees
Voir `src/schemas.py`. Referent : Agent Explicateur/Orchestration.

## Donnees et limites
Les sources actuellement integrees, les jeux de donnees recommandes et les
donnees operationnelles a obtenir de l'Etat sont decrits dans `data/README.md`.
Le benchmark international USD/tonne n'est pas le prix CIF tunisien. Les
previsions et besoins affiches sont indicatifs et ne remplacent pas les stocks,
contrats et plans de securite alimentaire officiels.

## Lancer
  .\.venv\Scripts\python.exe -m src.graph
  .\.venv\Scripts\python.exe -m streamlit run src/dashboard/app.py
