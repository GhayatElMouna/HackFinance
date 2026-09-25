# Sous-agents Variables

Chaque fichier = un sous-agent independant pour une variable du document
T17 (priorite 1). Meme patron pour les 4 : `run() -> VariableOutput`.

| Sous-agent | Source | Frequence |
|---|---|---|
| prix_international_agent | Banque mondiale, FMI | Mensuelle |
| brent_agent | Banque mondiale, FMI / Trading Economics | Journaliere/mensuelle |
| usd_tnd_agent | BCT | Journaliere |
| inflation_agent | INS, FMI | Mensuelle |

**Variables prevues mais non codees pour la demo** (priorite 1 restante,
a ajouter selon le meme patron si le temps le permet) : Importations,
Code SH, Quantite, Pays d origine, Date d importation - ces 5 sont en
realite des champs par transaction douaniere, deja portes par les
sous-agents Matieres Premieres (INS COMEX), pas des series a part.

**Responsable** : [nom]
