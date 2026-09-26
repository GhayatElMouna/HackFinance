from src.agents.collector_agent.official_sources import Collector, latest_fred_observation
from src.schemas import VariableOutput


def run() -> VariableOutput:
    """Latest international aluminum benchmark, sourced directly from FRED."""
    observed_on, value = latest_fred_observation(Collector(), "PALUMUSDM")
    return VariableOutput(
        nom="prix_international", date=observed_on, valeur=value,
        unite="USD/tonne aluminium (FRED PALUMUSDM)", source="FRED PALUMUSDM",
        is_synthetic=False,
    )
