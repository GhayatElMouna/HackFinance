"""Generation du rapport PDF Boussole Budgetaire."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from fpdf import FPDF

from src.schemas import PipelineResult


def _safe(text: str) -> str:
    """FPDF core fonts: strip characters outside latin-1."""
    cleaned = (
        (text or "")
        .replace("—", "-")
        .replace("–", "-")
        .replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .encode("latin-1", errors="replace")
        .decode("latin-1")
    )
    # Evite les tokens trop longs qui cassent multi_cell
    return " ".join(cleaned.split())


class BoussoleReport(FPDF):
    def header(self) -> None:
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(15, 110, 86)
        self.cell(0, 8, "Boussole Budgetaire / TrendGov", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(90, 90, 90)
        self.cell(
            0,
            6,
            _safe(f"Rapport genere le {datetime.now().strftime('%Y-%m-%d %H:%M')}"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}/{{nb}}", align="C")


def _section(pdf: BoussoleReport, title: str) -> None:
    pdf.ln(3)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(26, 35, 50)
    pdf.cell(0, 8, _safe(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(15, 110, 86)
    pdf.set_line_width(0.4)
    y = pdf.get_y()
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(3)
    pdf.set_x(pdf.l_margin)


def _text(pdf: BoussoleReport, text: str, size: int = 10, style: str = "") -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", style, size)
    pdf.set_text_color(30, 30, 30)
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.multi_cell(usable, 5, _safe(text))
    pdf.set_x(pdf.l_margin)


def build_pdf_report(result: PipelineResult) -> bytes:
    pdf = BoussoleReport(format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    _section(pdf, "1. Predictions de tendance")
    if not result.feature_predictor.predictions:
        _text(pdf, "Aucune prediction disponible.")
    for prediction in result.feature_predictor.predictions:
        line = (
            f"- {prediction.matiere}: {prediction.tendance} "
            f"(confiance {prediction.confiance * 100:.1f}%"
            f"{', influence budgetaire' if prediction.budget_a_influence else ''})"
        )
        _text(pdf, line)

    _section(pdf, "2. Explications")
    for explanation in result.explanations:
        _text(pdf, explanation.matiere.capitalize(), size=11, style="B")
        _text(pdf, explanation.texte_explicatif)
        if explanation.feature_importances:
            weights = ", ".join(
                f"{key}={value}%" for key, value in explanation.feature_importances.items()
            )
            _text(pdf, f"Poids indicatifs: {weights}", size=9, style="I")

    if result.lois_finances:
        _section(pdf, "3. Lois de Finances - indicateurs budgetaires")
        _text(
            pdf,
            f"Mode: {result.lois_finances.source_mode} | "
            f"Annees: {', '.join(map(str, result.lois_finances.annees_analysees))}",
        )
        features = result.lois_finances.features_budgetaires or {}
        labels = {
            "depense_budget_mdt": "Depense budget (MDT)",
            "variation_budget_pct": "Variation (%)",
            "variation_budget_3ans_pct": "Variation 3 ans (%)",
            "score_pression_budgetaire": "Pression budgetaire (0-1)",
            "total_subventions_mdt_latest": "Total subventions (MDT)",
        }
        for key, value in features.items():
            label = key
            for prefix, nice in labels.items():
                if key.startswith(prefix):
                    suffix = key[len(prefix) :].lstrip("_") or ""
                    label = f"{nice}" + (f" - {suffix}" if suffix else "")
                    break
            _text(pdf, f"- {label}: {value}")

        for year_summary in result.lois_finances.resumes_par_annee:
            _text(pdf, f"LF {year_summary.annee}", size=10, style="B")
            if year_summary.resume:
                _text(pdf, year_summary.resume[:500], size=9)

    _section(pdf, "4. Meteo & actualites")
    wn = result.weather_news
    _text(
        pdf,
        f"Zone: {wn.zone} | Score risque: {wn.score_risque} | Source: {wn.source}",
    )
    for event in wn.events[:12]:
        _text(
            pdf,
            f"- [{event.date.isoformat()}] impact={event.score_impact:+.2f} | {event.titre}",
            size=9,
        )

    _section(pdf, "5. Donnees collectees (apercu)")
    for variable in result.collector.variables:
        _text(
            pdf,
            f"- {variable.nom}: {variable.valeur} {variable.unite} "
            f"({variable.date.isoformat()} | {variable.source})",
            size=9,
        )
    for material in result.collector.matieres_premieres:
        if not material.points:
            continue
        point = material.points[-1]
        _text(
            pdf,
            f"- {material.matiere}: {point.prix_unitaire} "
            f"({point.date.isoformat()} | {material.source})",
            size=9,
        )

    buffer = BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()
