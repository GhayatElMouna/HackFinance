# Jeux de donnees du ble

## Sources integrees

### World Bank Pink Sheet

- Fichier local: `data/raw/worldbank_commodity_prices_monthly.xlsx`
- Source: [Commodity Markets](https://www.worldbank.org/en/research/commodity-markets)
- Frequence: mensuelle, en USD nominaux.
- Series chargees: `Wheat, US HRW`, `Crude oil, Brent` et `Urea`.
- Usage: reference de prix international et chocs de facteurs pour les scenarios.
- Limite: le benchmark US HRW n'est pas une cotation d'achat tunisienne ni un prix CIF; qualite, origine, fret, assurance et contrat doivent etre ajoutes pour estimer le prix rendu.

### FAOSTAT Food Balances

- Archive locale: `data/raw/faostat_food_balances_africa.zip`
- CSV extrait: `data/raw/faostat_food_balances_africa/FoodBalanceSheets_E_Africa.csv`
- Source: [FAOSTAT Food Balances](https://www.fao.org/faostat/en/#data/FBS)
- Frequence: annuelle. L'archive actuellement utilisee va de 2010 a 2023.
- Filtre: `Area=Tunisia`, `Item=Wheat and products`.
- Indicateurs utilises: disponibilite interieure, usage alimentaire, production et importations.
- Usage: niveau historique de demande pour estimer la couverture et le besoin d'achat.
- Limite: ces donnees ne remplacent ni les stocks courants des silos, ni les arrivees contractees, ni les previsions de recolte de la campagne en cours.

## Sources a raccorder pour une decision operationnelle

1. [AMIS](https://www.amis-outlook.org/) et [USDA WASDE](https://www.usda.gov/oce/commodity/wasde): bilans mondiaux mensuels, production, consommation, stocks, exportations, importations et revisions de previsions. Conserver la date de publication et la version de chaque bulletin pour eviter d'utiliser une revision inconnue a la date de prevision.
2. [INS Tunisie](https://www.ins.tn/) et [UN Comtrade](https://comtradeapi.un.org/): importations de la Tunisie par mois, code SH, pays partenaire, quantite et valeur. Le code SH 1001 sert a filtrer le ble; ses sous-positions doivent etre conservees pour separer les qualites. Verifier la couverture mensuelle et les unites avant integration.
3. Banque Centrale de Tunisie: taux USD/TND historique, aligne sur le mois et la date de disponibilite. Ce facteur convertit le cout en dinars; il ne deplace pas a lui seul le cours mondial en dollars.
4. INS Tunisie: indice des prix a la consommation. A utiliser pour le contexte budgetaire et domestique, pas comme substitut aux fondamentaux du marche mondial.
5. Stocks et achats de l'Etat: stocks utilisables par qualite et silo, contrats signes, cargaisons et dates d'arrivee, pertes de stockage, recolte previsionnelle et reserve strategique cible. Ces donnees operationnelles doivent etre fournies par les services concernes; elles ne sont pas derivees de FAOSTAT.
6. Meteo des principales regions productrices/exportatrices: anomalies de precipitation et temperature pendant les stades culturaux. La meteo tunisienne seule n'explique pas l'offre mondiale.
7. Fret et primes d'achat: cout de transport maritime, assurance de guerre, cout portuaire et ecart de qualite/origine. Utiliser les contrats/achats tunisiens quand ils sont disponibles; sinon exposer ces valeurs comme hypotheses.

## Calculs et garde-fous

- Le prix international doit etre predit en USD/tonne; le prix CIF tunisien est une cible distincte a estimer avec les valeurs douanieres ou les contrats d'achat.
- Le besoin indicatif est: demande sur l'horizon + stock tampon cible - stocks utilisables - arrivees contractees - recolte attendue, borne a zero.
- En attendant les donnees courantes de l'Etat, le tableau de bord demande ces valeurs a l'utilisateur et affiche l'annee du bilan FAOSTAT utilise.
- Les sensibilites historiques sont des co-mouvements, pas des effets causaux. Tout choc de fret, meteo, geopolitiques ou prime CIF saisi manuellement doit rester marque comme hypothese.
- Le choix de modele utilise les premieres 18 origines temporelles; les 6 suivantes servent de test final. Un score faible sur ce holdout signale que les modeles disponibles ne suffisent pas a prevoir la direction.