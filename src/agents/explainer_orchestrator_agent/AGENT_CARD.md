# Agent Explicateur + Orchestration LangGraph

**Role** : agent fusionne en deux responsabilites.
1. Explicabilite : calcule le feature importance (SHAP) et genere un
   texte explicatif en langage naturel par matiere, a partir des
   predictions.
2. Orchestration : cable le graphe LangGraph complet (Collecteur ->
   Meteo/News -> Feature+Predicteur -> Explicateur) et est **referent
   du contrat de donnees** (schemas.py) - toute modification de
   structure doit passer par cette personne.

**Input** : `FeaturePredictorOutput`, modele entraine

**Output** : `List[ExplainerOutput]` + `PipelineResult` (voir schemas.py)

**Dependances** : shap, langgraph

**Responsable** : [nom] - referent contrat inter-agents
