# Agent Meteo/News

**Role** : recuperer previsions meteo sur les zones de production
pertinentes (ex. zones cerealieres pour le ble) et des titres d
actualite recents, en deriver un score de risque simple (0 a 1) utilise
comme feature exogene par l agent Feature Engineer + Predicteur.

**Input** : zone geographique, fenetre temporelle

**Output** : `WeatherNewsOutput` (voir schemas.py)

**Dependances** : requests (API meteo + API news/RSS)

**Responsable** : [nom]
