from src.schemas import VariableOutput


def run() -> VariableOutput:
    """Sous-agent USD/TND (T17, priorite 1)."""
    # TODO: appeler API BCT (GOSDMX)
    return VariableOutput(
        nom="usd_tnd", date="2026-09-01", valeur=0.0,
        unite="TND", source="TODO", is_synthetic=True,
    )
