from src.schemas import FeaturePredictorOutput, ExplainerOutput


def run(feature_predictor: FeaturePredictorOutput) -> list[ExplainerOutput]:
    """Point d entree de l agent Explicateur."""
    # TODO: calculer SHAP par matiere, generer le texte explicatif
    return [
        ExplainerOutput(matiere=p.matiere, texte_explicatif="TODO", feature_importances={})
        for p in feature_predictor.predictions
    ]
