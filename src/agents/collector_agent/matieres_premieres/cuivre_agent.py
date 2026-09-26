from src.schemas import MatierePremiereOutput, MarketDataPoint


def run() -> MatierePremiereOutput:
    """Sous-agent Cuivre (HS 74) - INS COMEX + World Bank/IMF + BCT."""
    # TODO: charger INS COMEX, calculer prix_unitaire = valeur / quantite
    points = [
        MarketDataPoint(
            date="2026-09-01", prix_unitaire=0.0, quantite=0.0,
            valeur_importee=0.0, code_sh="74", pays_origine=None,
        )
    ]
    return MatierePremiereOutput(matiere="cuivre", points=points, source="TODO", is_synthetic=True)
