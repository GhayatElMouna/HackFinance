from src.data.worldbank_prices import FACTOR_CATALOG
from src.schemas import FeaturePredictorOutput, ExplainerOutput


def run(feature_predictor: FeaturePredictorOutput) -> list[ExplainerOutput]:
    """Point d entree de l agent Explicateur."""
    explanations: list[ExplainerOutput] = []
    for p in feature_predictor.predictions:
        if p.modele == "sarimax" and p.forecast:
            last_hist = p.historique[-1].yhat if p.historique else None
            last_fc = p.forecast[-1].yhat
            delta = p.variation_prevue_pct
            if delta == 0.0 and last_hist and last_hist != 0:
                delta = (last_fc - last_hist) / last_hist * 100
            delta_txt = f" ({delta:+.1f} % sur l'horizon)" if delta is not None else ""
            attrs = p.attributs or {}

            drivers = []
            used_keys = []
            for key, meta in FACTOR_CATALOG.items():
                var_key = f"exog_{key}_var_3m_pct"
                if var_key in attrs:
                    drivers.append(f"{meta['label_fr']} {attrs[var_key]:+.1f} % sur 3 mois")
                    used_keys.append(key)
            drivers_txt = "; ".join(drivers) if drivers else "aucun facteur exogène (SARIMA)"
            facteurs_txt = ", ".join(
                FACTOR_CATALOG[k]["label_fr"] for k in used_keys
            ) if used_keys else "aucun"

            texte = (
                f"Prévision SARIMAX sur le minerai de fer (Pink Sheet, Banque mondiale). "
                f"Facteurs retenus : {facteurs_txt}. "
                f"Tendance prévue : {p.tendance}{delta_txt}. "
                f"Confiance du modèle : {p.confiance:.0%}. "
                f"Contexte récent : {drivers_txt}."
            )
            # Importances simples : poids egal sur facteurs actifs + serie + saison
            n = max(len(used_keys), 1)
            weight = 0.50 / n
            importances = {"serie_prix_fer": 0.40, "saisonnalite_mensuelle": 0.10}
            for k in used_keys:
                importances[k] = round(weight, 3)
            if not used_keys:
                importances["serie_prix_fer"] = 0.75
                importances["saisonnalite_mensuelle"] = 0.25
        else:
            texte = (
                f"Prédiction stub pour {p.matiere} "
                f"(tendance={p.tendance}, confiance={p.confiance:.0%})."
            )
            importances = {}
        explanations.append(
            ExplainerOutput(
                matiere=p.matiere,
                texte_explicatif=texte,
                feature_importances=importances,
            )
        )
    return explanations
