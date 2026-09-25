# Sous-agents Matieres Premieres

Chaque fichier = un sous-agent independant pour une matiere premiere
reelle du guide hackathon. Meme patron : `run() -> MatierePremiereOutput`.

| Sous-agent | Code HS | Sources | Statut |
|---|---|---|---|
| ble_agent | 1001 | INS COMEX, World Bank, FAOSTAT/AMIS, ERA5-Land, BCT | code en profondeur |
| petrole_agent | 2709/2710 | INS COMEX, World Bank/IMF, BCT | code en profondeur |
| plastiques_agent | HS 39 | INS COMEX, World Bank/IMF energie, Min. Finances | stub |
| aluminium_agent | HS 76 | INS COMEX, World Bank/IMF, BCT | stub |

**Matieres prevues non codees pour la demo** (meme patron a dupliquer si
le temps le permet) : Mais (HS 1005), Cuivre (HS 74), Fer/Acier (HS 72).

**Point de vigilance (guide hackathon)** : ne pas agreger des produits
heterogenes sous un meme prix unitaire ; descendre au HS6 si besoin.

**Responsable** : [nom]
