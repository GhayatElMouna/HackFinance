# Boussole Budgetaire

Systeme d alerte precoce sur les tendances de prix des matieres
premieres subventionnees, via un pipeline multi-agents hierarchique
(LangGraph).

## Architecture des agents

- **Agent Collecteur** (parent)
  - Sous-agents Variables : prix_international, brent, usd_tnd, inflation
  - Sous-agents Matieres Premieres : benchmarks web pour ble, petrole, aluminium
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

## Collecter l'aluminium
Depuis le dossier `HackFinance`, lancer :

    python -m src.agents.collector_agent.official_sources --aluminium

La collecte enregistre le prix mondial mensuel FRED (`PALUMUSDM`) et la serie
historique du World Bank Pink Sheet dans `data/raw/`, avec les reponses brutes
et un manifeste. Le Pink Sheet actuellement publie peut etre en retard sur FRED.
Les importations tunisiennes detaillees HS76 ne sont pas disponibles sur la page
INS publique : exporter le cube Commerce exterieur depuis le portail INS.

## Sources web utilisees par les agents
Le pipeline interroge directement FRED pour le prix aluminium (`PALUMUSDM`) et
le Brent (`DCOILBRENTEU`), la Banque mondiale pour USD/TND (`PA.NUS.FCRF`) et
l'inflation (`FP.CPI.TOTL.ZG`), le Pink Sheet pour le ble US HRW, et Open-Meteo
pour le risque meteorologique. Le prix d'approvisionnement aluminium utilise le
benchmark FRED converti avec le dernier taux USD/TND disponible; la source et
les dates sont affichees.

Les series de ble, petrole et aluminium sont des benchmarks internationaux,
pas les quantites/prix d'import tunisiens. Les stocks/consommations restent des
donnees internes saisies dans l'interface. Plastiques n'a pas encore de source
de cotation fiable branchee; le flux d'actualites est egalement indisponible.
Les erreurs de sources sont affichees au lieu d'etre remplacees par des zeros.

Le bouton de prevision aluminium utilise l'historique FRED reel. Il choisit
entre le dernier prix et la moyenne des trois derniers mois sur une fenetre de
selection chronologique de 12 mois, puis evalue le choix sur les 12 mois suivants
jamais utilises pour la selection. Il faut au moins 36 mois et l'interface affiche
le prix prevu et les erreurs MAE/MAPE du test final.
La plage historique affichee n'est pas un intervalle de confiance; la projection
peut rester stable si c'est le meilleur resultat observe au backtest.
