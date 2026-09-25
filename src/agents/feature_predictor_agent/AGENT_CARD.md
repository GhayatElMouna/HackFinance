# Agent Feature Engineer + Predicteur

**Role** : agent fusionne en deux etapes internes.
1. Feature engineering : fusionne les sorties du Collecteur (variables +
   matieres premieres) et du Meteo/News ; calcule moyennes mobiles,
   volatilite glissante, momentum, variation FX par matiere.
2. Prediction : classifie la tendance (hausse / baisse / stable-volatile)
   par matiere via XGBoost (baseline), avec indice de confiance.

**Input** : `CollectorOutput`, `WeatherNewsOutput`

**Output** : `FeaturePredictorOutput` (voir schemas.py)

**Dependances** : pandas, numpy, xgboost, scikit-learn

**Responsable** : [nom]
