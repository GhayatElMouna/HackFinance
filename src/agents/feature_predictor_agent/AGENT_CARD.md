# Agent Feature Engineer + Predicteur

**Role** : agent fusionne en deux etapes internes.
1. Feature engineering : fusionne les sorties du Collecteur (variables +
   matieres premieres) et du Meteo/News ; calcule moyennes mobiles,
   volatilite glissante, momentum, variation FX par matiere.
2. Prediction : baseline explicable qui classe la tendance (hausse / baisse /
   stable-volatile) sur les derniers prix observes, avec un score de soutien
   indicatif. Pas de modele supervise tant que les historiques ne sont pas
   associes a des resultats etiquetes.
3. Prevision de prix mensuelle : compare dernier prix et moyenne mobile 3 mois
   sur une fenetre de selection chronologique de 12 mois, puis mesure la methode
   retenue sur les 12 mois suivants (test final jamais utilise pour la selection).
   Il faut au moins 36 mois valides; l'horizon est de 1 a 12 mois.

La prevision expose MAE et MAPE hors echantillon ainsi qu'une plage basee sur
l'erreur absolue mediane observee. Cette plage n'est pas un intervalle de
confiance. Si le dernier prix gagne le backtest, la projection est plate; le
modele ne force pas une hausse ou une baisse sans signal valide.

**Input** : `CollectorOutput`, `WeatherNewsOutput`

**Output** : `FeaturePredictorOutput` (voir schemas.py)

**Dependances** : pandas, numpy, xgboost, scikit-learn

**Responsable** : [nom]
