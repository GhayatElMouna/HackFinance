from src.schemas import MatierePremiereOutput, MarketDataPoint


def run() -> MatierePremiereOutput:
    """Sous-agent Ble (HS 1001) - INS COMEX + World Bank + FAOSTAT/AMIS + ERA5-Land."""
    # TODO: charger INS COMEX, calculer prix_unitaire = valeur / quantite
    points = [
        MarketDataPoint(
            date="2026-09-01", prix_unitaire=0.0, quantite=0.0,
            valeur_importee=0.0, code_sh="1001", pays_origine=None,
        )
    ]
    return MatierePremiereOutput(matiere="ble", points=points, source="TODO", is_synthetic=True)
