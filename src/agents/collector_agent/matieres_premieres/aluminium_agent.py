from src.schemas import MatierePremiereOutput

# STUB - a completer si le temps le permet (meme patron que ble_agent/petrole_agent)
# Sources prevues : INS COMEX (HS 76), World Bank/IMF, BCT


def run() -> MatierePremiereOutput:
    """Sous-agent Aluminium (HS 76) - stub."""
    return MatierePremiereOutput(matiere="aluminium", points=[], source="non_implemente", is_synthetic=True)
