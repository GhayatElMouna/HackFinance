from datetime import date

from src.agents.collector_agent.official_sources import (
    Collector,
    collect_fred_market_series,
)
from src.schemas import MatierePremiereOutput, MarketDataPoint


def run() -> MatierePremiereOutput:
    """Fetch the daily Europe Brent benchmark from FRED, not Tunisian imports."""
    frame = collect_fred_market_series(
        Collector(), "DCOILBRENTEU", "USD/barrel", "D"
    )
    points = [
        MarketDataPoint(
            date=date.fromisoformat(row.period),
            prix_unitaire=float(row.value),
            quantite=0.0,
            valeur_importee=0.0,
            code_sh="GLOBAL",
            pays_origine="Europe Brent benchmark",
            type_donnee="benchmark",
        )
        for row in frame.itertuples(index=False)
    ]
    return MatierePremiereOutput(
        matiere="petrole",
        points=points,
        source="FRED DCOILBRENTEU (USD/barrel)",
        is_synthetic=False,
    )
