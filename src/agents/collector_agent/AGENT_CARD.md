# Agent Collecteur (Marche)

**Role** : agent parent qui orchestre deux sous-branches et agrege leurs
sorties en un seul `CollectorOutput` transmis a l aval du pipeline.

**Sous-agents** :
- `variables/` : 4 sous-agents, un par variable reelle du document T17
  (prix international, Brent, USD/TND, inflation)
- `matieres_premieres/` : sous-agents par matiere reelle du guide
  hackathon (aluminium FRED; autres series selon disponibilite des sources)

**Input** : liste des matieres premieres a collecter, fenetre temporelle

**Output** : `CollectorOutput` (voir schemas.py)

Les sources actuellement interrogees directement sont FRED (`PALUMUSDM`,
`DCOILBRENTEU`) et l'API World Bank (`PA.NUS.FCRF`, `FP.CPI.TOTL.ZG`). Les erreurs
de source et les matieres sans source reelle configuree sont exposees dans
`collection_errors`; aucune valeur nulle n'est presentee comme observation reelle.

**Dependances** : requests, pandas

**Responsable** : [nom binome], referent contrat inter-agents : Explicateur/orchestration
