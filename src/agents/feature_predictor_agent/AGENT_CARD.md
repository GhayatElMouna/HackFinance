# Agent Feature Engineer + Predicteur

**Role** : deux etapes exposees separement dans le graph LangGraph.
1. Feature engineering : fusionne Collecteur + Meteo/News + **Lois de Finances** ;
   calcule moyennes mobiles, volatilite, momentum, variation FX, et features
   budgetaires (`depense_budget_mdt`, `variation_budget_pct`,
   `score_pression_budgetaire`).
2. Prediction : classifie la tendance (hausse / baisse / stable-volatile) avec
   score de confiance ; le facteur budgetaire peut renforcer ou basculer
   legerement la tendance (`budget_a_influence`).
3. Prevision de prix mensuelle (optionnelle) : baseline backtestee (dernier prix
   vs moyenne 3 mois).

**Input** : `CollectorOutput`, `WeatherNewsOutput`, `FinanceLawOutput | None`

**Output** : `FeaturePredictorOutput`

**API** :
- `build_features(...)` — noeud Feature Engineer
- `predict_trends(...)` — noeud Predicteur
- `run(...)` — raccourci fusionne (compat)
