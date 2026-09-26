"""Sous-orchestrateur Variables (sous-graph LangGraph)."""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.collector_agent.variables import (
    brent_agent,
    inflation_agent,
    prix_international_agent,
    usd_tnd_agent,
)
from src.schemas import VariableOutput


def _merge_dicts(left: dict | None, right: dict | None) -> dict:
    return {**(left or {}), **(right or {})}


class VariablesState(TypedDict):
    variables: Annotated[list[dict], operator.add]
    errors: Annotated[list[str], operator.add]
    agent_status: Annotated[dict[str, str], _merge_dicts]


def _run_variable(name: str, runner) -> dict:
    try:
        result: VariableOutput = runner()
        return {
            "variables": [result.model_dump(mode="json")],
            "agent_status": {f"var_{name}": "done"},
        }
    except Exception as error:
        return {
            "errors": [f"{name}: {error}"],
            "agent_status": {f"var_{name}": "error"},
        }


def node_prix_international(_state: VariablesState) -> dict:
    return _run_variable("prix_international", prix_international_agent.run)


def node_brent(_state: VariablesState) -> dict:
    return _run_variable("brent", brent_agent.run)


def node_usd_tnd(_state: VariablesState) -> dict:
    return _run_variable("usd_tnd", usd_tnd_agent.run)


def node_inflation(_state: VariablesState) -> dict:
    return _run_variable("inflation", inflation_agent.run)


def build_variables_graph():
    builder = StateGraph(VariablesState)
    builder.add_node("prix_international", node_prix_international)
    builder.add_node("brent", node_brent)
    builder.add_node("usd_tnd", node_usd_tnd)
    builder.add_node("inflation", node_inflation)
    for node in ("prix_international", "brent", "usd_tnd", "inflation"):
        builder.add_edge(START, node)
        builder.add_edge(node, END)
    return builder.compile()


def run() -> tuple[list[VariableOutput], list[str], dict[str, str]]:
    graph = build_variables_graph()
    final = graph.invoke(
        {
            "variables": [],
            "errors": [],
            "agent_status": {
                "var_prix_international": "idle",
                "var_brent": "idle",
                "var_usd_tnd": "idle",
                "var_inflation": "idle",
            },
        }
    )
    variables = [VariableOutput.model_validate(item) for item in final.get("variables", [])]
    return variables, final.get("errors", []), final.get("agent_status", {})
