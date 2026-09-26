from src.agents.collector_agent.official_sources import Collector, latest_wb_observation
from src.schemas import VariableOutput


def run() -> VariableOutput:
    """Latest annual official USD/TND rate from the World Bank API."""
    observed_on, value = latest_wb_observation(Collector(), "PA.NUS.FCRF")
    return VariableOutput(
        nom="usd_tnd", date=observed_on, valeur=value,
        unite="TND/USD (moyenne annuelle)",
        source="World Bank PA.NUS.FCRF", is_synthetic=False,
    )
