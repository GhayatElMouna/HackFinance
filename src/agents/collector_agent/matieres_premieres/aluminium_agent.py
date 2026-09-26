from datetime import date

from src.agents.collector_agent.official_sources import Collector, collect_fred_aluminium
from src.schemas import MarketDataPoint, MatierePremiereOutput


def run() -> MatierePremiereOutput:
    """Fetch the live FRED global aluminum benchmark, not Tunisian import data."""
    frame = collect_fred_aluminium(Collector())
    points = [
        MarketDataPoint(
            date=date.fromisoformat(f"{row.period}-01"),
            prix_unitaire=float(row.value),
            quantite=0.0,
            valeur_importee=0.0,
            code_sh="GLOBAL",
            pays_origine="Global benchmark",
            type_donnee="benchmark",
        )
        for row in frame.itertuples(index=False)
    ]
    return MatierePremiereOutput(
        matiere="aluminium",
        points=points,
        source="FRED PALUMUSDM (USD/metric ton)",
        is_synthetic=False,
    )
