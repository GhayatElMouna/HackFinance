from src.schemas import MatierePremiereOutput

# Aucun benchmark public de prix des plastiques n'est configure.


def run() -> MatierePremiereOutput:
    """Return unavailable until an official HS39 series is supplied."""
    return MatierePremiereOutput(
        matiere="plastiques",
        points=[],
        source="aucune serie web fiable configuree pour HS39",
        is_synthetic=True,
    )
