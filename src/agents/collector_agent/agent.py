"""
Agent Collecteur (parent) : sous-orchestrateurs Variables + Matieres Premieres.
Conserve `run(matieres)` pour compatibilite; le graph LangGraph principal
appelle aussi les orchestrateurs individuellement.
"""
from src.agents.collector_agent.matieres_orchestrator import agent as matieres_orchestrator
from src.agents.collector_agent.variables_orchestrator import agent as variables_orchestrator
from src.schemas import CollectorOutput


def run(matieres: list[str]) -> CollectorOutput:
    """Point d entree de l agent Collecteur parent (Variables + MP en sous-graphs)."""
    variables, var_errors, _ = variables_orchestrator.run()
    materials, mp_errors, _ = matieres_orchestrator.run(matieres)
    return CollectorOutput(
        variables=variables,
        matieres_premieres=materials,
        collection_errors=[*var_errors, *mp_errors],
    )
