# Agent Meteo/News

**Role** : combiner
1. prevision Open-Meteo a 7 jours (risque meteo 0-1)
2. actualites NewsAPI (`https://newsapi.org/`) filtrees sur les matieres
3. scoring d'impact optionnel via LLM Gemini (`GEMINI_API_KEY`),
   sinon heuristique mots-cles haussiers/baissiers

**Input** : `zone: str`, `matieres: list[str] | None`

**Output** : `WeatherNewsOutput`

**Variables d'environnement** :
- `NEWS_API_KEY` (obligatoire pour les news)
- `GEMINI_API_KEY` (optionnel, scoring LLM — defaut provider)
- `LLM_MODEL` (defaut `gemini-2.5-flash`)

**Responsable** : orchestration
