# Lois de Finances — documents d'entree

Placez ici les PDF (ou fichiers texte) des 3 dernieres lois de finances tunisiennes :

- `lf_2024.pdf` (ou `loi_finances_2024.pdf`)
- `lf_2025.pdf`
- `lf_2026.pdf`

L'agent `lois_finances_agent` :

1. Charge d'abord les extraits structures `extraits_curated.json` (toujours disponibles pour la demo).
2. Si des PDF/TXT sont presents, extrait le texte (chunking) et enrichit l'analyse.
3. Si `OPENAI_API_KEY` (ou `LLM_API_KEY`) est defini, un LLM resume les depenses/subventions par matiere.
4. Sinon, l'analyse reste regle + curated (pipeline 100 % local).

Formats acceptes : `.pdf`, `.txt`, `.md`.
