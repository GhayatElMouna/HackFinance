from src.schemas import MatierePremiereOutput

# STUB - a completer si le temps le permet (meme patron que ble_agent/petrole_agent)
# Sources prevues : INS COMEX (HS 39), World Bank/IMF (petrole/gaz en amont), Min. Finances


def run() -> MatierePremiereOutput:
    """Sous-agent Plastiques (HS 39) - stub."""
    return MatierePremiereOutput(matiere="plastiques", points=[], source="non_implemente", is_synthetic=True)
