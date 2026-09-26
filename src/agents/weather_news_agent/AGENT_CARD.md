# Agent Meteo/News

**Role** : recuperer directement une prevision Open-Meteo a 7 jours pour une
zone tunisienne et deriver un score de risque meteorologique (0 a 1) utilise
comme feature exogene par l'agent Feature Engineer + Predicteur.

**Input** : zone geographique, fenetre temporelle

**Output** : `WeatherNewsOutput` (voir schemas.py)

**Source active** : Open-Meteo geocoding et forecast, sans cle API.

**Limite** : le flux d'actualites n'est pas branche; les evenements et le score
representent uniquement la meteo. Les erreurs de collecte sont remontees dans
`WeatherNewsOutput.collection_errors`.

**Dependances** : requests

**Responsable** : [nom]
