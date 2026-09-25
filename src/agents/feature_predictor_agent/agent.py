from src.schemas import CollectorOutput, WeatherNewsOutput, FeaturePredictorOutput


def run(collector: CollectorOutput, weather_news: WeatherNewsOutput) -> FeaturePredictorOutput:
    """Point d entree de l agent Feature Engineer + Predicteur."""
    # TODO etape 1 : calculer les FeatureRow reelles a partir de collector + weather_news
    # TODO etape 2 : entrainer/charger XGBoost par matiere, predire tendance + confiance
    return FeaturePredictorOutput(features=[], predictions=[])
