# Sous-agents Matieres Premieres

Chaque fichier = un sous-agent independant pour une matiere premiere
reelle du guide hackathon. Meme patron : `run() -> MatierePremiereOutput`.

Orchestres via `matieres_orchestrator` (sous-graph LangGraph).

| Sous-agent | Code HS | Sources | Statut |
|---|---|---|---|
| ble_agent | 1001 | World Bank Pink Sheet, ble US HRW | benchmark web actif |
| petrole_agent | 2709/2710 | FRED Brent Europe | benchmark web actif |
| plastiques_agent | HS 39 | aucune serie publique fiable branchee | indisponible |
| aluminium_agent | HS 76 | FRED PALUMUSDM | benchmark web actif |
| cuivre_agent | HS 74 | World Bank Copper (`copper_monthly.csv`) | benchmark local |
| fer_acier_agent | HS 72 | World Bank Iron ore | benchmark actif |

Les series web sont des prix de reference internationaux, pas des declarations
d'importation tunisiennes.

**Responsable** : Collecteur / orchestration
