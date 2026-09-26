# Agent Predicteur Plastiques

**Role** : prevoit la log-variation a trois mois et une fourchette de prix
10-90 %, avec trois `HistGradientBoostingRegressor` a perte quantile. Corrige
l'ordre des quantiles, compare les variations aux baselines sans changement et
Brent, calcule les importances par permutation et genere trois scenarios.

**Entrees** : table `features_plastiques.csv` produite par l'agent Feature
Engineer Plastiques; les entrees source sont des fichiers locaux CSV/XLSX.

**Sorties** : contrat Pydantic local `PlasticsPredictionOutput`, fichier
`data/processed/prediction_plastiques.json`, table des importances et resultat
affiche par `python -m src.agents.plastics_predictor_agent.agent`.

**Methode** : validation walk-forward `TimeSeriesSplit` avec `gap=3`, MAE,
direction, couverture 10-90 %, et entrainement final sur toutes les observations
etiquetees. Une sortie est produite par code SH observe, ou une sortie proxy.

**Limites** : le proxy n'est pas un prix de transaction; la couverture cible
theorique est proche de 80 % mais n'est pas garantie. Le resultat inclut la cible,
les sources absentes, la derniere date exploitable et le statut de comparaison
aux baselines. Le modele ne fournit pas d'explication causale.