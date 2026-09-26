"""
Orchestrateur — focus fer/acier.
"""
from src.agents.collector_agent import agent as collector_agent
from src.agents.weather_news_agent import agent as weather_news_agent
from src.agents.feature_predictor_agent import agent as feature_predictor_agent
from src.agents.explainer_orchestrator_agent import agent as explainer_agent
from src.schemas import PipelineResult


def run_pipeline(
    matieres: list[str],
    zone: str = "mondial",
    horizon: int = 3,
    facteurs: list[str] | None = None,
    annee_debut: int = 2010,
) -> PipelineResult:
    collector_output = collector_agent.run(matieres)
    weather_news_output = weather_news_agent.run(zone)
    feature_predictor_output = feature_predictor_agent.run(
        collector_output,
        weather_news_output,
        horizon=horizon,
        facteurs=facteurs,
        annee_debut=annee_debut,
    )
    explanations = explainer_agent.run(feature_predictor_output)

    return PipelineResult.model_validate(
        {
            "collector": collector_output.model_dump(),
            "weather_news": weather_news_output.model_dump(),
            "feature_predictor": feature_predictor_output.model_dump(),
            "explanations": [e.model_dump() for e in explanations],
        }
    )


if __name__ == "__main__":
    result = run_pipeline(["fer_acier"], "zones industrielles Tunisie", horizon=3)
    pred = result.feature_predictor.predictions[0]
    print(pred.matiere, pred.tendance, pred.confiance, pred.modele, len(pred.forecast))
