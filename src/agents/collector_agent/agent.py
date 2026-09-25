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
    variables = [
        prix_international_agent.run(),
        brent_agent.run(),
        usd_tnd_agent.run(),
        inflation_agent.run(),
    ]

    matieres_map = {
        "ble": ble_agent.run,
        "petrole": petrole_agent.run,
        "plastiques": plastiques_agent.run,
        "aluminium": aluminium_agent.run,
    }
    matieres_premieres = [
        matieres_map[m]() for m in matieres if m in matieres_map
    ]

    return CollectorOutput(variables=variables, matieres_premieres=matieres_premieres)
