# Agent Predicteur Plastiques

**Role** : prevoit la log-variation a trois mois en comparant les modeles
`HistGradientBoostingRegressor` quantiles et Ridge en validation walk-forward.
Si aucun candidat ne bat la baseline « aucun changement », le central reste le
prix actuel. L'intervalle est calibre a 80 % par conformalisation des residus
walk-forward precedents, avec fenetre glissante de 60 observations.

**Entrees** : table `features_plastiques.csv` produite par l'agent Feature
Engineer Plastiques; les entrees source sont des fichiers locaux CSV/XLSX.

**Sorties** : contrat Pydantic local `PlasticsPredictionOutput`, fichier
`data/processed/prediction_plastiques.json`, table des importances et resultat
affiche par `python -m src.agents.plastics_predictor_agent.agent`.

**Methode** : validation walk-forward `TimeSeriesSplit` avec `gap=3`, MAE,
direction, couverture brute et calibree. Le benchmark Brent utilise uniquement
son rendement des trois mois precedents. Les scenarios du proxy appliquent les
chocs directement aux composantes normalisees de l'indice.

**Limites** : le proxy n'est pas un prix de transaction; la calibration conforme
est empirique et sa couverture future n'est pas garantie. Le resultat inclut la
cible, les sources absentes, la derniere date exploitable et la selection du
modele. Le modele ne fournit pas d'explication causale.