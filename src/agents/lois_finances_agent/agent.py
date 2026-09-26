"""Agent Lois de Finances — analyse des 3 dernieres LF tunisiennes (2024-2026)."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.schemas import BudgetLine, FinanceLawOutput, FinanceLawYearSummary

ROOT = Path(__file__).resolve().parents[3]
LOIS_DIR = ROOT / "data" / "lois_finances"
CURATED_PATH = LOIS_DIR / "extraits_curated.json"
TARGET_YEARS = (2024, 2025, 2026)

MATIERE_KEYWORDS = {
    "petrole": [
        "petrole",
        "pétrole",
        "carburant",
        "carburants",
        "energie",
        "énergie",
        "hydrocarbure",
        "steg",
        "electricite",
        "électricité",
    ],
    "ble": ["ble", "blé", "cereale", "céréale", "cereales", "céréales", "pain", "farine"],
    "aluminium": ["aluminium", "aluminum"],
    "plastiques": ["plastique", "plastiques"],
}


def _load_curated() -> dict[str, Any]:
    if not CURATED_PATH.exists():
        raise FileNotFoundError(f"Extraits curated introuvables: {CURATED_PATH}")
    return json.loads(CURATED_PATH.read_text(encoding="utf-8"))


def _find_documents() -> dict[int, Path]:
    """Map year -> local PDF/TXT if present."""
    found: dict[int, Path] = {}
    if not LOIS_DIR.exists():
        return found
    patterns = [
        r"(?:lf|loi[_-]?finances?|loi[_-]?de[_-]?finances?)[_-]?(\d{4})",
        r"(\d{4})",
    ]
    for path in sorted(LOIS_DIR.iterdir()):
        if path.suffix.lower() not in {".pdf", ".txt", ".md"}:
            continue
        if path.name.lower().startswith("readme"):
            continue
        name = path.stem.lower()
        for pattern in patterns:
            match = re.search(pattern, name)
            if match:
                year = int(match.group(1))
                if year in TARGET_YEARS and year not in found:
                    found[year] = path
                break
    return found


def _extract_pdf_text(path: Path, max_chars: int = 80_000) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    chunks: list[str] = []
    total = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        if not text.strip():
            continue
        chunks.append(text)
        total += len(text)
        if total >= max_chars:
            break
    return "\n".join(chunks)[:max_chars]


def _extract_text_document(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return _extract_pdf_text(path)
    return path.read_text(encoding="utf-8", errors="ignore")[:80_000]


def _chunk_text(text: str, chunk_size: int = 3500, overlap: int = 200) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    chunks = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        chunks.append(cleaned[start:end])
        if end >= len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks


def _keyword_hits(text: str, matiere: str) -> int:
    lower = text.lower()
    return sum(lower.count(keyword.lower()) for keyword in MATIERE_KEYWORDS.get(matiere, []))


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=8))
def _llm_summarize(chunks: list[str], year: int) -> str | None:
    """Optional LLM enrichment via OpenAI-compatible Chat Completions API."""
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        return None
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    sample = "\n\n".join(chunks[:4])
    prompt = (
        f"Tu analyses la Loi de Finances tunisienne {year}. "
        "Extrais en francais un resume structure (5-8 phrases) des depenses/subventions "
        "liees au petrole/energie, ble/cereales et autres matieres premieres subventionnees. "
        "Mentionne les montants si presents. Pas d'invention de chiffres absents du texte.\n\n"
        f"TEXTE:\n{sample}"
    )
    response = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "temperature": 0.1,
            "messages": [
                {
                    "role": "system",
                    "content": "Tu es un analyste budgetaire tunisien. Reponds en francais.",
                },
                {"role": "user", "content": prompt},
            ],
        },
        timeout=60,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return (content or "").strip() or None


def _build_features(summaries: list[FinanceLawYearSummary]) -> dict[str, float]:
    features: dict[str, float] = {}
    by_matiere: dict[str, list[tuple[int, float, float | None]]] = {}
    for summary in summaries:
        for line in summary.lignes:
            if not line.matiere:
                continue
            by_matiere.setdefault(line.matiere, []).append(
                (summary.annee, line.montant_mdt, line.variation_pct)
            )

    for matiere, rows in by_matiere.items():
        rows = sorted(rows, key=lambda item: item[0])
        latest_amount = rows[-1][1]
        first_amount = rows[0][1]
        variation_3ans = (
            (latest_amount / first_amount - 1.0) * 100.0 if first_amount else 0.0
        )
        latest_var = rows[-1][2] if rows[-1][2] is not None else variation_3ans
        # Pression budgetaire: niveau relatif + direction recente (0-1)
        niveau = min(max(latest_amount / 5000.0, 0.0), 1.0)
        direction = min(max((latest_var or 0.0) / 20.0, -1.0), 1.0)
        pression = min(max(0.5 * niveau + 0.5 * (direction + 1.0) / 2.0, 0.0), 1.0)
        features[f"depense_budget_mdt_{matiere}"] = round(latest_amount, 2)
        features[f"variation_budget_pct_{matiere}"] = round(float(latest_var or 0.0), 2)
        features[f"variation_budget_3ans_pct_{matiere}"] = round(variation_3ans, 2)
        features[f"score_pression_budgetaire_{matiere}"] = round(pression, 4)

    if summaries and summaries[-1].total_subventions_mdt is not None:
        features["total_subventions_mdt_latest"] = float(summaries[-1].total_subventions_mdt)
    return features


def _tendances(features: dict[str, float]) -> dict[str, str]:
    tendances: dict[str, str] = {}
    for key, value in features.items():
        if not key.startswith("variation_budget_3ans_pct_"):
            continue
        matiere = key.replace("variation_budget_3ans_pct_", "")
        if value > 3:
            tendances[matiere] = "hausse_depenses_budgetaires"
        elif value < -3:
            tendances[matiere] = "baisse_depenses_budgetaires"
        else:
            tendances[matiere] = "stable_depenses_budgetaires"
    return tendances


def _from_curated(data: dict[str, Any]) -> list[FinanceLawYearSummary]:
    summaries: list[FinanceLawYearSummary] = []
    for year_block in data.get("annees", []):
        annee = int(year_block["annee"])
        if annee not in TARGET_YEARS:
            continue
        lignes = [
            BudgetLine(
                annee=annee,
                poste=line["poste"],
                matiere=line.get("matiere"),
                montant_mdt=float(line["montant_mdt"]),
                variation_pct=line.get("variation_pct"),
                commentaire=line.get("commentaire", ""),
            )
            for line in year_block.get("lignes", [])
        ]
        summaries.append(
            FinanceLawYearSummary(
                annee=annee,
                source_document=year_block.get("source_document", f"LF {annee}"),
                total_subventions_mdt=year_block.get("total_subventions_mdt"),
                lignes=lignes,
                resume=year_block.get("resume", ""),
            )
        )
    return sorted(summaries, key=lambda item: item.annee)


def run(matieres: list[str] | None = None) -> FinanceLawOutput:
    """Charge curated (+ PDF optionnels) et produit un resume structure exploitable."""
    warnings: list[str] = []
    mode = "curated"
    curated = _load_curated()
    summaries = _from_curated(curated)
    documents = _find_documents()

    if documents:
        mode = "hybrid"
        for year, path in sorted(documents.items()):
            try:
                text = _extract_text_document(path)
                chunks = _chunk_text(text)
                if not chunks:
                    warnings.append(f"LF {year}: document vide ou non extractible ({path.name})")
                    continue
                llm_resume = None
                try:
                    llm_resume = _llm_summarize(chunks, year)
                except Exception as error:
                    warnings.append(f"LF {year}: LLM indisponible ({error})")
                hits = {
                    matiere: _keyword_hits(text, matiere)
                    for matiere in ("petrole", "ble", "aluminium", "plastiques")
                }
                enrichment = (
                    f"Document local {path.name}: mentions "
                    + ", ".join(f"{k}={v}" for k, v in hits.items() if v > 0)
                )
                for summary in summaries:
                    if summary.annee != year:
                        continue
                    summary.source_document = f"{summary.source_document} + {path.name}"
                    if llm_resume:
                        mode = "llm"
                        summary.resume = f"{summary.resume}\n[LLM] {llm_resume}".strip()
                    else:
                        summary.resume = f"{summary.resume}\n[{enrichment}]".strip()
            except Exception as error:
                warnings.append(f"LF {year}: echec parsing {path.name}: {error}")
    else:
        warnings.append(
            "Aucun PDF/TXT trouve dans data/lois_finances/; "
            "analyse basee sur extraits_curated.json"
        )

    features = _build_features(summaries)
    # Filtrer les features aux matieres demandees si precise
    if matieres:
        selected = set(matieres)
        features = {
            key: value
            for key, value in features.items()
            if key == "total_subventions_mdt_latest"
            or any(key.endswith(f"_{matiere}") for matiere in selected)
        }

    return FinanceLawOutput(
        annees_analysees=[summary.annee for summary in summaries],
        resumes_par_annee=summaries,
        tendances_par_matiere=_tendances(features),
        features_budgetaires=features,
        source_mode=mode,
        warnings=warnings,
        is_synthetic=False,
    )
