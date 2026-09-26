from datetime import date

from src.agents.collector_agent.official_sources import (
    Collector,
    collect_wb_pinksheet,
    filter_wb_benchmark,
)
from src.schemas import MatierePremiereOutput, MarketDataPoint


def run() -> MatierePremiereOutput:
    """Fetch the World Bank US Hard Red Winter wheat global price benchmark."""
    collector = Collector()
    data = filter_wb_benchmark(
        collect_wb_pinksheet(collector), "Wheat, US HRW", "wheat_us_hrw"
    )
    points = [
        MarketDataPoint(
            date=date(int(row.period[:4]), int(row.period[-2:]), 1),
            prix_unitaire=float(row.value),
            quantite=0.0,
            valeur_importee=0.0,
            code_sh="GLOBAL",
            pays_origine="World Bank benchmark (US HRW)",
            type_donnee="benchmark",
        )
        for row in data.itertuples(index=False)
    ]
    return MatierePremiereOutput(
        matiere="ble",
        points=points,
        source="World Bank Pink Sheet Wheat, US HRW (USD/mt)",
        is_synthetic=False,
    )
