# Agent Feature Engineer + Predicteur

**Role** : agent fusionne en deux etapes internes.
1. Feature engineering : fusionne les sorties du Collecteur (variables +
   matieres premieres) et du Meteo/News ; calcule moyennes mobiles,
   volatilite glissante, momentum, variation FX par matiere.
2. Prediction :
   - `fer_acier` : forecast SARIMAX (saisonnalite mensuelle, Brent en
     exogene) + classification tendance / confiance + series
     historique/forecast pour le dashboard.
   - autres matieres : stub (XGBoost prevu).

**Input** : `CollectorOutput`, `WeatherNewsOutput`, `horizon` (mois)

**Output** : `FeaturePredictorOutput` (voir schemas.py)

**Dependances** : pandas, numpy, statsmodels, xgboost, scikit-learn

**Responsable** : [nom]
