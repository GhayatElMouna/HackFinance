# Agent Explicateur + Orchestration LangGraph

**Role** : agent fusionne en deux responsabilites.
1. Explicabilite : genere un texte en francais par matiere a partir de la
   tendance observee, des features recentes et des previsions mensuelles. Les
   poids momentum/volatilite sont indicatifs, pas des valeurs SHAP ni des
   importances d'un modele supervise.
2. Orchestration : cable le graphe LangGraph complet (Collecteur ->
   Meteo/News -> Feature+Predicteur -> Explicateur) et est **referent
   du contrat de donnees** (schemas.py) - toute modification de
   structure doit passer par cette personne.

**Input** : `FeaturePredictorOutput`, modele entraine

**Output** : `List[ExplainerOutput]` + `PipelineResult` (voir schemas.py)

**Dependances** : shap, langgraph

**Responsable** : [nom] - referent contrat inter-agents
