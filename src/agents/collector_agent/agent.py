"""
Agent Collecteur (parent) : appelle les sous-agents Variables et
Matieres Premieres, puis agrege leurs sorties.
"""
from src.schemas import CollectorOutput
from src.agents.collector_agent.variables import (
    prix_international_agent, brent_agent, usd_tnd_agent, inflation_agent,
)
from src.agents.collector_agent.matieres_premieres import (
    ble_agent, petrole_agent, plastiques_agent, aluminium_agent,
)


def run(matieres: list[str]) -> CollectorOutput:
    """Point d entree de l agent Collecteur parent."""
    variables = []
    collection_errors = []
    variable_agents = {
        "prix_international": prix_international_agent.run,
        "brent": brent_agent.run,
        "usd_tnd": usd_tnd_agent.run,
        "inflation": inflation_agent.run,
    }
    for name, agent_run in variable_agents.items():
        try:
            variables.append(agent_run())
        except Exception as error:
            collection_errors.append(f"{name}: {error}")

    matieres_map = {
        "ble": ble_agent.run,
        "petrole": petrole_agent.run,
        "plastiques": plastiques_agent.run,
        "aluminium": aluminium_agent.run,
    }
    matieres_premieres = []
    for name in matieres:
        agent_run = matieres_map.get(name)
        if agent_run is None:
            collection_errors.append(f"{name}: aucun agent de collecte configure")
            continue
        try:
            material = agent_run()
            matieres_premieres.append(material)
            if material.is_synthetic or not material.points:
                collection_errors.append(
                    f"{name}: aucune source web reelle n'est configuree pour cette matiere"
                )
        except Exception as error:
            collection_errors.append(f"{name}: {error}")

    return CollectorOutput(
        variables=variables,
        matieres_premieres=matieres_premieres,
        collection_errors=collection_errors,
    )
