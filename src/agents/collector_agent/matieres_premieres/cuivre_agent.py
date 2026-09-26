import pandas as pd
from src.schemas import MatierePremiereOutput, MarketDataPoint


def run() -> MatierePremiereOutput:
    """Sous-agent Cuivre (HS 74) - approxime via prix mondial x taux de change (pas de COMEX)."""
    world_price = pd.read_csv("data/raw/world_price_cuivre.csv", parse_dates=["date"])
    usd_tnd = pd.read_csv("data/raw/usd_tnd.csv", parse_dates=["date"])
    world_price = world_price[world_price["date"] >= usd_tnd["date"].min()]

    df = pd.merge_asof(
        world_price.sort_values("date")[["date", "price"]].rename(columns={"price": "prix_mondial_usd_mt"}),
        usd_tnd.sort_values("date")[["date", "usd_tnd"]],
        on="date",
    )
    df["prix_unitaire"] = (df["prix_mondial_usd_mt"] / 1000) * df["usd_tnd"]  # $/mt -> $/kg -> TND/kg

    points = [
        MarketDataPoint(
            date=row["date"].date(),
            prix_unitaire=row["prix_unitaire"],
            quantite=0.0,          # non disponible sans COMEX
            valeur_importee=0.0,   # non disponible sans COMEX
            code_sh="74",
            pays_origine=None,
        )
        for _, row in df.iterrows()
    ]

    return MatierePremiereOutput(
        matiere="cuivre", points=points,
        source="World Bank (prix mondial) + BCT (USD/TND) - proxy prix de reference, pas de donnees COMEX reelles",
        is_synthetic=False,
    )