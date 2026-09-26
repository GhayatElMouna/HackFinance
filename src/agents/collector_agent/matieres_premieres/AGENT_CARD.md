# Sous-agents Matieres Premieres

Chaque fichier = un sous-agent independant pour une matiere premiere
reelle du guide hackathon. Meme patron : `run() -> MatierePremiereOutput`.

| Sous-agent | Code HS | Sources | Statut |
|---|---|---|---|
| ble_agent | 1001 | World Bank Pink Sheet, ble US HRW | benchmark web actif |
| petrole_agent | 2709/2710 | FRED Brent Europe | benchmark web actif |
| plastiques_agent | HS 39 | aucune serie publique fiable branchee | indisponible |
| aluminium_agent | HS 76 | FRED PALUMUSDM | benchmark web actif |

Les series web sont des prix de reference internationaux, pas des declarations
d'importation tunisiennes. Le detail COMEX HS x origine x quantite doit venir
du cube INS/Douane et n'est pas reconstruit a partir des benchmarks.

**Matieres prevues non codees pour la demo** (meme patron a dupliquer si
le temps le permet) : Mais (HS 1005), Cuivre (HS 74), Fer/Acier (HS 72).

**Point de vigilance (guide hackathon)** : ne pas agreger des produits
heterogenes sous un meme prix unitaire ; descendre au HS6 si besoin.

**Responsable** : [nom]
