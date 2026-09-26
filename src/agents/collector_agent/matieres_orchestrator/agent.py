"""Sous-orchestrateur Matieres Premieres (sous-graph LangGraph)."""
from __future__ import annotations

import operator
from typing import Annotated, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from src.agents.collector_agent.matieres_premieres import (
    aluminium_agent,
    ble_agent,
    cuivre_agent,
    fer_acier_agent,
    petrole_agent,
    plastiques_agent,
)
from src.schemas import MatierePremiereOutput

MATIERE_RUNNERS: dict[str, Callable[[], MatierePremiereOutput]] = {
    "ble": ble_agent.run,
    "petrole": petrole_agent.run,
    "plastiques": plastiques_agent.run,
    "aluminium": aluminium_agent.run,
    "cuivre": cuivre_agent.run,
    "fer_acier": fer_acier_agent.run,
}


def _merge_dicts(left: dict | None, right: dict | None) -> dict:
    return {**(left or {}), **(right or {})}


class MatieresState(TypedDict):
    matieres: list[str]
    matieres_premieres: Annotated[list[dict], operator.add]
    errors: Annotated[list[str], operator.add]
    agent_status: Annotated[dict[str, str], _merge_dicts]
    _current_matiere: str


def _run_one(state: MatieresState) -> dict:
    name = state.get("_current_matiere") or ""
    status_key = f"mp_{name}"
    runner = MATIERE_RUNNERS.get(name)
    if runner is None:
        return {
            "errors": [f"{name}: aucun agent de collecte configure"],
            "agent_status": {status_key: "error"},
        }
    try:
        material = runner()
        errors: list[str] = []
        if material.is_synthetic or not material.points:
            errors.append(
                f"{name}: aucune source web reelle n'est configuree pour cette matiere"
            )
        return {
            "matieres_premieres": [material.model_dump(mode="json")],
            "errors": errors,
            "agent_status": {status_key: "done"},
        }
    except Exception as error:
        return {
            "errors": [f"{name}: {error}"],
            "agent_status": {status_key: "error"},
        }


def _dispatch(state: MatieresState) -> list[Send]:
    return [
        Send("collect_one", {**state, "_current_matiere": name})
        for name in state.get("matieres") or []
    ]


def build_matieres_graph():
    builder = StateGraph(MatieresState)
    builder.add_node("collect_one", _run_one)
    builder.add_conditional_edges(START, _dispatch, ["collect_one"])
    builder.add_edge("collect_one", END)
    return builder.compile()


def run(matieres: list[str]) -> tuple[list[MatierePremiereOutput], list[str], dict[str, str]]:
    graph = build_matieres_graph()
    initial_status = {f"mp_{name}": "idle" for name in matieres}
    final = graph.invoke(
        {
            "matieres": matieres,
            "matieres_premieres": [],
            "errors": [],
            "agent_status": initial_status,
            "_current_matiere": "",
        }
    )
    materials = [
        MatierePremiereOutput.model_validate(item)
        for item in final.get("matieres_premieres", [])
    ]
    return materials, final.get("errors", []), final.get("agent_status", {})
