# Agent Lois de Finances

**Role** : lire et analyser les Lois de Finances tunisiennes 2024, 2025 et 2026
pour en extraire les depenses / subventions pertinentes (petrole, ble, etc.).

**Input** : liste optionnelle de matieres (`list[str]`)

**Output** : `FinanceLawOutput` (JSON structure) avec :
- resumes par annee
- lignes budgetaires (`BudgetLine`)
- `features_budgetaires` (montants, variations, score de pression)
- tendances par matiere

**Sources** :
1. `data/lois_finances/extraits_curated.json` (toujours)
2. PDF/TXT locaux dans `data/lois_finances/` si fournis
3. LLM optionnel si `OPENAI_API_KEY` / `LLM_API_KEY` est defini

**Responsable** : orchestration / budget
