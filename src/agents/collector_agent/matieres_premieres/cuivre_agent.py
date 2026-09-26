"""Sous-agent Cuivre (HS 74) — benchmark World Bank Pink Sheet local."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.schemas import MarketDataPoint, MatierePremiereOutput

ROOT = Path(__file__).resolve().parents[4]
COPPER_CSV = ROOT / "data" / "raw" / "copper_monthly.csv"


def run() -> MatierePremiereOutput:
    if not COPPER_CSV.exists():
        raise FileNotFoundError(
            f"Serie cuivre introuvable: {COPPER_CSV}. "
            "Lancer la collecte World Bank ou placer copper_monthly.csv."
        )
    frame = pd.read_csv(COPPER_CSV, parse_dates=["date"])
    if "price" not in frame.columns:
        raise ValueError("copper_monthly.csv doit contenir une colonne price")
    points = [
        MarketDataPoint(
            date=row.date.date(),
            prix_unitaire=float(row.price),
            quantite=0.0,
            valeur_importee=0.0,
            code_sh="74",
            pays_origine="World",
            type_donnee="benchmark",
        )
        for row in frame.itertuples(index=False)
        if pd.notna(row.price)
    ]
    return MatierePremiereOutput(
        matiere="cuivre",
        points=points,
        source="World Bank Pink Sheet (Copper, $/mt) — data/raw/copper_monthly.csv",
        is_synthetic=False,
    )
