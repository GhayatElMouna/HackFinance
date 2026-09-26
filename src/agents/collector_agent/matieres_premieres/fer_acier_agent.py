"""Sous-agent Fer/Acier (HS 72) — prix mondial (proxy minerai de fer World Bank)."""
from __future__ import annotations

import os

from src.data.worldbank_prices import load_commodity_series
from src.schemas import MarketDataPoint, MatierePremiereOutput


def run() -> MatierePremiereOutput:
    """
    Charge la serie mensuelle Iron ore CFR Chine (proxy prix fer/acier mondial).
    Source : World Bank Commodity Markets Pink Sheet.
    """
    refresh = os.getenv("REFRESH_WORLDBANK", "0") == "1"
    series, source, is_synthetic = load_commodity_series("Iron ore", refresh=refresh)

    points = [
        MarketDataPoint(
            date=row.date.date(),
            prix_unitaire=float(row.price),
            quantite=1.0,
            valeur_importee=float(row.price),
            code_sh="72",
            pays_origine="World",
        )
        for row in series.itertuples(index=False)
    ]

    return MatierePremiereOutput(
        matiere="fer_acier",
        points=points,
        source=source,
        is_synthetic=is_synthetic,
    )
