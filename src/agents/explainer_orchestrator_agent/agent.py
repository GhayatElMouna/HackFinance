from src.schemas import FeaturePredictorOutput, ExplainerOutput


def run(feature_predictor: FeaturePredictorOutput) -> list[ExplainerOutput]:
    """Explique le modele retenu, le backtest et les limites des scenarios."""
    explanations = []
    for prediction in feature_predictor.predictions:
        if prediction.prix_prevu is None or prediction.date_cible is None:
            continue
        accuracy = prediction.precision_historique
        accuracy_text = (
            f"{accuracy:.0%} sur {prediction.observations_validation} origines"
            if accuracy is not None
            else "non disponible"
        )
        mape_text = (
            f"{prediction.mape_validation_pct:.1f}%"
            if prediction.mape_validation_pct is not None
            else "non disponible"
        )
        baseline_text = (
            f"{prediction.mape_baseline_validation_pct:.1f}%"
            if prediction.mape_baseline_validation_pct is not None
            else "non disponible"
        )
        prophet_metrics = prediction.comparaison_modeles.get("Prophet", {})
        prophet_mape = prophet_metrics.get("mape_pct")
        prophet_text = f"{prophet_mape:.1f}%" if prophet_mape is not None else "non disponible"
        explanations.append(
            ExplainerOutput(
                matiere=prediction.matiere,
                texte_explicatif=(
                    f"Le modele retenu ({prediction.modele}) prevoit une tendance "
                    f"{prediction.tendance} au "
                    f"{prediction.date_cible:%m/%Y}, a {prediction.prix_prevu:.2f} "
                    f"{prediction.unite}, avec un intervalle a 80% de "
                    f"{prediction.prix_bas:.2f} a {prediction.prix_haut:.2f}, calibre sur "
                    f"{prediction.observations_selection} origines de selection. "
                    f"Le test final porte sur {prediction.observations_validation} origines. "
                    f"Son MAPE est {mape_text} "
                    f"contre {baseline_text} pour le momentum 3 mois; le MAPE Prophet est "
                    f"{prophet_text}. La justesse directionnelle retenue est {accuracy_text}. "
                    "Les sensibilites Brent/uree sont des co-mouvements historiques et ne prouvent pas "
                    "une causalite. Le modele n'integre pas encore "
                    "les importations tunisiennes, le change, le fret, les stocks, "
                    "la meteo ou les chocs geopolitiques; ce n'est pas une relation causale."
                ),
                feature_importances={},
            )
        )
    return explanations
