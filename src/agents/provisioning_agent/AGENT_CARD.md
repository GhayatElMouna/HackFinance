# Agent de provisionnement

**Role** : calculer une recommandation de reapprovisionnement a partir du stock
physique, de la consommation quotidienne, du delai fournisseur, du stock en
transit et du stock de securite.

**Sorties** : couverture en jours, seuil de declenchement, quantite a commander,
niveau d'urgence, date conseillee et cout indicatif si un prix TND/tonne est fourni.
Sans prix manuel, le prix de reference est lu en direct sur FRED (`PALUMUSDM`)
et converti avec le dernier taux annuel World Bank (`PA.NUS.FCRF`). Le resultat
conserve la source et la date de l'observation de prix.

**Limites** : l'agent ne passe aucune commande. Les entrees d'inventaire doivent
etre fournies par l'utilisateur ou un systeme de stock; elles ne sont pas
deduites du prix mondial de l'aluminium.