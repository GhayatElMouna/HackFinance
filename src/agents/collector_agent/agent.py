"""
Agent Collecteur (parent) — focus fer/acier.
Construit uniquement des dicts pour eviter les conflits Pydantic (hot-reload).
"""
from src.schemas import CollectorOutput
from src.agents.collector_agent.matieres_premieres import fer_acier_agent


def run(matieres: list[str] | None = None) -> CollectorOutput:
    """Point d entree de l agent Collecteur parent (fer/acier uniquement)."""
    _ = matieres  # ignore ; demo centree fer/acier
    raw = fer_acier_agent.run()
    payload = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
    # Re-serialisation JSON pour couper toute identite de classe Pydantic
    import json
    from datetime import date, datetime

    def _default(o):
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        raise TypeError(type(o))

    clean = json.loads(json.dumps(payload, default=_default))
    return CollectorOutput.model_validate(
        {
            "variables": [],
            "matieres_premieres": [clean],
        }
    )
