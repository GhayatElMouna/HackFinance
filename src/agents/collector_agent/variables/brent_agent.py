from src.schemas import VariableOutput


def run() -> VariableOutput:
    """Sous-agent Brent (T17, priorite 1)."""
    # TODO: appeler API Banque mondiale/FMI ou Trading Economics
    return VariableOutput(
        nom="brent", date="2026-09-01", valeur=0.0,
        unite="$/baril", source="TODO", is_synthetic=True,
    )
