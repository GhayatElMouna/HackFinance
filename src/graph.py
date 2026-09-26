"""
Orchestrateur LangGraph.
Flux : Collecteur (avec sous-agents Variables + Matieres Premieres) et
Meteo/News en parallele -> Feature Engineer + Predicteur -> Explicateur.
"""
from src.agents.collector_agent import agent as collector_agent
from src.agents.weather_news_agent import agent as weather_news_agent
from src.agents.feature_predictor_agent import agent as feature_predictor_agent
from src.agents.explainer_orchestrator_agent import agent as explainer_agent
from src.schemas import PipelineResult, WeatherNewsOutput


def run_pipeline(matieres: list[str], zone: str) -> PipelineResult:
    collector_output = collector_agent.run(matieres)
    try:
        weather_news_output = weather_news_agent.run(zone)
    except Exception as error:
        weather_news_output = WeatherNewsOutput(
            score_risque=0.0,
            events=[],
            zone=zone,
            source="meteo indisponible",
            is_synthetic=True,
            collection_errors=[str(error)],
        )
    feature_predictor_output = feature_predictor_agent.run(collector_output, weather_news_output)
    explanations = explainer_agent.run(feature_predictor_output)

    return PipelineResult(
        collector=collector_output,
        weather_news=weather_news_output,
        feature_predictor=feature_predictor_output,
        explanations=explanations,
    )


if __name__ == "__main__":
    result = run_pipeline(["ble", "petrole"], "zones cerealieres nord Tunisie")
    print(result)
