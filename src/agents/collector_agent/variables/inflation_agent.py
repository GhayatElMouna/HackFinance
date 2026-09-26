from src.agents.collector_agent.official_sources import Collector, latest_wb_observation
from src.schemas import VariableOutput


def run() -> VariableOutput:
    """Latest annual Tunisia consumer-price inflation from the World Bank."""
    observed_on, value = latest_wb_observation(Collector(), "FP.CPI.TOTL.ZG")
    return VariableOutput(
        nom="inflation", date=observed_on, valeur=value,
        unite="% (annuel)", source="World Bank FP.CPI.TOTL.ZG", is_synthetic=False,
    )
