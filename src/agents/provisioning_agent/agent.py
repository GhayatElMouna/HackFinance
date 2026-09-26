"""Calculate a transparent inventory replenishment recommendation."""
from __future__ import annotations

from datetime import date, timedelta
from math import isfinite

from src.agents.collector_agent.official_sources import latest_aluminium_price_tnd_t
from src.schemas import ProvisioningOutput, ProvisioningRequest


def run(request: ProvisioningRequest, today: date | None = None) -> ProvisioningOutput:
    """Recommend reorder quantity from stock, demand, lead time, and safety stock.

    This agent plans replenishment only; it never creates or sends a purchase order.
    """
    numeric_values = {
        "stock_disponible_t": request.stock_disponible_t,
        "consommation_journaliere_t": request.consommation_journaliere_t,
        "quantite_en_transit_t": request.quantite_en_transit_t,
    }
    if request.prix_unitaire_tnd_t is not None:
        numeric_values["prix_unitaire_tnd_t"] = request.prix_unitaire_tnd_t
    if any(not isfinite(value) for value in numeric_values.values()):
        raise ValueError("Les quantites et prix doivent etre des nombres finis")
    if any(value < 0 for value in numeric_values.values()):
        raise ValueError("Les quantites et prix ne peuvent pas etre negatifs")
    if request.consommation_journaliere_t <= 0:
        raise ValueError("La consommation journaliere doit etre superieure a zero")
    if request.delai_approvisionnement_jours < 0 or request.stock_securite_jours < 0:
        raise ValueError("Les delais et le stock de securite ne peuvent pas etre negatifs")

    stock_total = request.stock_disponible_t + request.quantite_en_transit_t
    couverture = stock_total / request.consommation_journaliere_t
    seuil = request.consommation_journaliere_t * (
        request.delai_approvisionnement_jours + request.stock_securite_jours
    )
    quantite = max(0.0, seuil - stock_total)
    quantite = round(quantite, 3)

    if quantite == 0:
        niveau = "aucun_besoin"
        date_commande = None
        justification = "Le stock disponible et en transit couvre le seuil de provisionnement."
    else:
        niveau = (
            "urgent"
            if couverture <= request.delai_approvisionnement_jours
            else "a_commander"
        )
        date_commande = today or date.today()
        justification = (
            "Commander maintenant pour couvrir le delai fournisseur et le stock de securite."
        )

    cout = (
        round(quantite * request.prix_unitaire_tnd_t, 3)
        if request.prix_unitaire_tnd_t is not None and quantite > 0
        else None
    )
    return ProvisioningOutput(
        matiere=request.matiere,
        couverture_jours=round(couverture, 2),
        seuil_declenchement_t=round(seuil, 3),
        quantite_a_commander_t=quantite,
        niveau_urgence=niveau,
        date_commande_recommandee=date_commande,
        cout_estime_tnd=cout,
        source_prix="Saisie utilisateur" if request.prix_unitaire_tnd_t is not None else None,
        justification=justification,
    )


def run_with_web_price(
    request: ProvisioningRequest, today: date | None = None
) -> ProvisioningOutput:
    """Use a live aluminum benchmark converted with latest annual USD/TND rate."""
    price_date, price_tnd_t, price_source = latest_aluminium_price_tnd_t()
    priced_request = request.model_copy(
        update={"prix_unitaire_tnd_t": price_tnd_t}
    )
    result = run(priced_request, today=today)
    return result.model_copy(
        update={"source_prix": price_source, "date_prix": price_date}
    )