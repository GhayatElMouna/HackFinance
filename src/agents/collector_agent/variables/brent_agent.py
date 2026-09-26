from src.agents.collector_agent.official_sources import Collector, latest_fred_observation
from src.schemas import VariableOutput


def run() -> VariableOutput:
    """Latest observed Europe Brent spot price from FRED."""
    observed_on, value = latest_fred_observation(Collector(), "DCOILBRENTEU")
    return VariableOutput(
        nom="brent", date=observed_on, valeur=value,
        unite="USD/baril", source="FRED DCOILBRENTEU", is_synthetic=False,
    )
