from src.schemas import VariableOutput


def run() -> VariableOutput:
    """Sous-agent Prix International (T17, priorite 1)."""
    # TODO: appeler API Banque mondiale/FMI (Commodity Markets Pink Sheet)
    return VariableOutput(
        nom="prix_international", date="2026-09-01", valeur=0.0,
        unite="USD", source="TODO", is_synthetic=True,
    )
