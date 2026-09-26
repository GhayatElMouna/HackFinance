# Agent Collecteur (Marche)

**Role** : agent parent qui orchestre deux sous-branches et agrege leurs
sorties en un seul `CollectorOutput` transmis a l aval du pipeline.

**Sous-agents** :
- `variables/` : 4 sous-agents, un par variable reelle du document T17
  (prix international, Brent, USD/TND, inflation)
- `matieres_premieres/` : sous-agents par matiere reelle du guide
  hackathon (ble, petrole codes en profondeur ; plastiques, aluminium
  en stub, extensible a mais/cuivre) ; fer_acier implemente (World Bank)

**Input** : liste des matieres premieres a collecter, fenetre temporelle

**Output** : `CollectorOutput` (voir schemas.py)

**Dependances** : requests, pandas

**Responsable** : [nom binome], referent contrat inter-agents : Explicateur/orchestration
