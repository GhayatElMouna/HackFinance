"""
Orchestrateur LangGraph principal — Boussole Budgetaire / TrendGov.

Flux:
  Collecteur (dispatch)
    ├─ Sous-orchestrateur Variables      ─┐
    ├─ Sous-orchestrateur Matieres Prem. ─┼─► merge Collecteur
    ├─ Agent Lois de Finances            ─┤
    └─ Agent Meteo/News                   ─┘
         → Feature Engineer → Predicteur → Explicateur
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, Callable, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.collector_agent.matieres_orchestrator import agent as matieres_orchestrator
from src.agents.collector_agent.variables_orchestrator import agent as variables_orchestrator
from src.agents.explainer_orchestrator_agent import agent as explainer_agent
from src.agents.feature_predictor_agent import agent as feature_predictor_agent
from src.agents.lois_finances_agent import agent as lois_finances_agent
from src.agents.weather_news_agent import agent as weather_news_agent
from src.schemas import (
    CollectorOutput,
    FeaturePredictorOutput,
    FeatureRow,
    FinanceLawOutput,
    MatierePremiereOutput,
    PipelineResult,
    VariableOutput,
    WeatherNewsOutput,
)

StatusCallback = Optional[Callable[[dict[str, str]], None]]


def _merge_dicts(left: dict | None, right: dict | None) -> dict:
    """Reducer pour fusionner les mises a jour paralleles de statuts."""
    return {**(left or {}), **(right or {})}


class PipelineState(TypedDict, total=False):
    matieres: list[str]
    zone: str
    horizon_mois: int
    agent_status: Annotated[dict[str, str], _merge_dicts]
    variables: list[dict]
    matieres_premieres: list[dict]
    lois_finances: dict | None
    weather_news: dict | None
    collection_errors: Annotated[list[str], operator.add]
    collector: dict | None
    features: list[dict]
    predictions: list[dict]
    price_forecasts: list[dict]
    explanations: list[dict]
    errors: Annotated[list[str], operator.add]


DEFAULT_STATUS = {
    "collecteur": "idle",
    "variables": "idle",
    "matieres_premieres": "idle",
    "lois_finances": "idle",
    "weather_news": "idle",
    "feature_engineer": "idle",
    "predicteur": "idle",
    "explicateur": "idle",
}


def node_collector_dispatch(_state: PipelineState) -> dict[str, Any]:
    return {
        "agent_status": {"collecteur": "running"},
        "collection_errors": [],
        "errors": [],
    }


def node_variables(_state: PipelineState) -> dict[str, Any]:
    try:
        variables, errors, sub_status = variables_orchestrator.run()
        status = {**sub_status, "variables": "done" if variables else "error"}
        if errors and not variables:
            status["variables"] = "error"
        return {
            "variables": [item.model_dump(mode="json") for item in variables],
            "collection_errors": errors,
            "agent_status": status,
        }
    except Exception as error:
        return {
            "collection_errors": [f"variables: {error}"],
            "agent_status": {"variables": "error"},
        }


def node_matieres(state: PipelineState) -> dict[str, Any]:
    matieres = state.get("matieres") or ["petrole"]
    try:
        materials, errors, sub_status = matieres_orchestrator.run(matieres)
        status = {
            **sub_status,
            "matieres_premieres": "done" if materials else "error",
        }
        return {
            "matieres_premieres": [item.model_dump(mode="json") for item in materials],
            "collection_errors": errors,
            "agent_status": status,
        }
    except Exception as error:
        return {
            "collection_errors": [f"matieres_premieres: {error}"],
            "agent_status": {"matieres_premieres": "error"},
        }


def node_lois_finances(state: PipelineState) -> dict[str, Any]:
    try:
        output = lois_finances_agent.run(state.get("matieres"))
        return {
            "lois_finances": output.model_dump(mode="json"),
            "agent_status": {"lois_finances": "done"},
            "collection_errors": list(output.warnings or []),
        }
    except Exception as error:
        return {
            "lois_finances": None,
            "errors": [f"lois_finances: {error}"],
            "agent_status": {"lois_finances": "error"},
        }


def node_weather(state: PipelineState) -> dict[str, Any]:
    zone = state.get("zone") or "zones cerealieres nord Tunisie"
    try:
        output = weather_news_agent.run(zone)
        return {
            "weather_news": output.model_dump(mode="json"),
            "agent_status": {"weather_news": "done"},
            "collection_errors": list(output.collection_errors or []),
        }
    except Exception as error:
        fallback = WeatherNewsOutput(
            score_risque=0.0,
            events=[],
            zone=zone,
            source="meteo indisponible",
            is_synthetic=True,
            collection_errors=[str(error)],
        )
        return {
            "weather_news": fallback.model_dump(mode="json"),
            "agent_status": {"weather_news": "error"},
            "collection_errors": [f"weather_news: {error}"],
        }


def node_collector_merge(state: PipelineState) -> dict[str, Any]:
    collector = CollectorOutput(
        variables=[VariableOutput.model_validate(item) for item in state.get("variables") or []],
        matieres_premieres=[
            MatierePremiereOutput.model_validate(item)
            for item in state.get("matieres_premieres") or []
        ],
        collection_errors=list(state.get("collection_errors") or []),
    )
    return {
        "collector": collector.model_dump(mode="json"),
        "agent_status": {"collecteur": "done"},
    }


def node_feature_engineer(state: PipelineState) -> dict[str, Any]:
    try:
        collector = CollectorOutput.model_validate(state["collector"])
        weather = WeatherNewsOutput.model_validate(state["weather_news"])
        lois = (
            FinanceLawOutput.model_validate(state["lois_finances"])
            if state.get("lois_finances")
            else None
        )
        features = feature_predictor_agent.build_features(collector, weather, lois)
        return {
            "features": [item.model_dump(mode="json") for item in features],
            "agent_status": {"feature_engineer": "done"},
        }
    except Exception as error:
        return {
            "features": [],
            "errors": [f"feature_engineer: {error}"],
            "agent_status": {"feature_engineer": "error"},
        }


def node_predicteur(state: PipelineState) -> dict[str, Any]:
    try:
        collector = CollectorOutput.model_validate(state["collector"])
        lois = (
            FinanceLawOutput.model_validate(state["lois_finances"])
            if state.get("lois_finances")
            else None
        )
        features = [FeatureRow.model_validate(item) for item in state.get("features") or []]
        horizon = int(state.get("horizon_mois") or 6)
        output = feature_predictor_agent.predict_trends(
            collector,
            features,
            lois_finances=lois,
            horizon_mois=horizon,
        )
        return {
            "predictions": [item.model_dump(mode="json") for item in output.predictions],
            "price_forecasts": [
                item.model_dump(mode="json") for item in output.price_forecasts
            ],
            "agent_status": {"predicteur": "done"},
        }
    except Exception as error:
        return {
            "predictions": [],
            "price_forecasts": [],
            "errors": [f"predicteur: {error}"],
            "agent_status": {"predicteur": "error"},
        }


def node_explicateur(state: PipelineState) -> dict[str, Any]:
    try:
        feature_output = FeaturePredictorOutput.model_validate(
            {
                "features": state.get("features") or [],
                "predictions": state.get("predictions") or [],
                "price_forecasts": state.get("price_forecasts") or [],
            }
        )
        lois = (
            FinanceLawOutput.model_validate(state["lois_finances"])
            if state.get("lois_finances")
            else None
        )
        explanations = explainer_agent.run(feature_output, lois_finances=lois)
        return {
            "explanations": [item.model_dump(mode="json") for item in explanations],
            "agent_status": {"explicateur": "done"},
        }
    except Exception as error:
        return {
            "explanations": [],
            "errors": [f"explicateur: {error}"],
            "agent_status": {"explicateur": "error"},
        }


def build_graph():
    builder = StateGraph(PipelineState)
    builder.add_node("collector_dispatch", node_collector_dispatch)
    builder.add_node("variables", node_variables)
    builder.add_node("matieres_premieres", node_matieres)
    builder.add_node("lois_finances", node_lois_finances)
    builder.add_node("weather_news", node_weather)
    builder.add_node("collector_merge", node_collector_merge)
    builder.add_node("feature_engineer", node_feature_engineer)
    builder.add_node("predicteur", node_predicteur)
    builder.add_node("explicateur", node_explicateur)

    builder.add_edge(START, "collector_dispatch")
    # Branches paralleles apres le dispatch Collecteur
    for branch in ("variables", "matieres_premieres", "lois_finances", "weather_news"):
        builder.add_edge("collector_dispatch", branch)
        builder.add_edge(branch, "collector_merge")
    builder.add_edge("collector_merge", "feature_engineer")
    builder.add_edge("feature_engineer", "predicteur")
    builder.add_edge("predicteur", "explicateur")
    builder.add_edge("explicateur", END)
    return builder.compile()


def _to_pipeline_result(final: dict[str, Any]) -> PipelineResult:
    collector = CollectorOutput.model_validate(
        final.get("collector")
        or {
            "variables": final.get("variables") or [],
            "matieres_premieres": final.get("matieres_premieres") or [],
            "collection_errors": final.get("collection_errors") or [],
        }
    )
    weather = WeatherNewsOutput.model_validate(
        final.get("weather_news")
        or {
            "score_risque": 0.0,
            "events": [],
            "zone": final.get("zone") or "",
            "is_synthetic": True,
        }
    )
    lois = (
        FinanceLawOutput.model_validate(final["lois_finances"])
        if final.get("lois_finances")
        else None
    )
    feature_predictor = FeaturePredictorOutput.model_validate(
        {
            "features": final.get("features") or [],
            "predictions": final.get("predictions") or [],
            "price_forecasts": final.get("price_forecasts") or [],
        }
    )
    from src.schemas import ExplainerOutput

    explanations = [
        ExplainerOutput.model_validate(item) for item in final.get("explanations") or []
    ]
    return PipelineResult(
        collector=collector,
        weather_news=weather,
        lois_finances=lois,
        feature_predictor=feature_predictor,
        explanations=explanations,
        agent_status=final.get("agent_status") or {},
    )


def run_pipeline(
    matieres: list[str],
    zone: str,
    horizon_mois: int = 1,
    status_callback: StatusCallback = None,
) -> PipelineResult:
    """Execute le pipeline LangGraph de bout en bout."""
    graph = build_graph()
    initial: PipelineState = {
        "matieres": matieres,
        "zone": zone,
        "horizon_mois": horizon_mois,
        "agent_status": dict(DEFAULT_STATUS),
        "variables": [],
        "matieres_premieres": [],
        "lois_finances": None,
        "weather_news": None,
        "collection_errors": [],
        "collector": None,
        "features": [],
        "predictions": [],
        "price_forecasts": [],
        "explanations": [],
        "errors": [],
    }

    if status_callback is None:
        final = graph.invoke(initial)
        return _to_pipeline_result(final)

    final_state: dict[str, Any] = dict(initial)
    for event in graph.stream(initial, stream_mode="updates"):
        for _node_name, update in event.items():
            if not isinstance(update, dict):
                continue
            for key, value in update.items():
                if key in {"collection_errors", "errors"} and isinstance(value, list):
                    final_state[key] = list(final_state.get(key) or []) + value
                elif key == "agent_status" and isinstance(value, dict):
                    merged = dict(final_state.get("agent_status") or {})
                    merged.update(value)
                    final_state[key] = merged
                    status_callback(merged)
                else:
                    final_state[key] = value
    return _to_pipeline_result(final_state)


if __name__ == "__main__":
    result = run_pipeline(["petrole"], "zones cerealieres nord Tunisie", horizon_mois=3)
    print("Statuts:", result.agent_status)
    print("Erreurs collecte:", result.collector.collection_errors)
    if result.lois_finances:
        print("Lois mode:", result.lois_finances.source_mode)
        print("Features budget:", result.lois_finances.features_budgetaires)
    for prediction in result.feature_predictor.predictions:
        print(
            f"{prediction.matiere}: {prediction.tendance} "
            f"(conf={prediction.confiance}, budget={prediction.budget_a_influence})"
        )
    for explanation in result.explanations:
        print(f"--- {explanation.matiere} ---")
        print(explanation.texte_explicatif[:400])
        print("importances:", explanation.feature_importances)
