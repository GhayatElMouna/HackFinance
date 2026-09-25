from src.schemas import VariableOutput


def run() -> VariableOutput:
    """Sous-agent Inflation (T17, priorite 1)."""
    # TODO: appeler API INS/FMI
    return VariableOutput(
        nom="inflation", date="2026-09-01", valeur=0.0,
        unite="%", source="TODO", is_synthetic=True,
    )
