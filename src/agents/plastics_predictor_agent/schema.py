"""Contrat Pydantic propre au predicteur plastiques."""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PlasticsPredictionOutput(BaseModel):
    """Sortie stable consommee ulterieurement par l'agent explicateur."""

    model_config = ConfigDict(extra="forbid")

    produit: str = "plastiques"
    cible_utilisee: str
    code_sh: str | None = None
    date_reference: date
    horizon_mois: int = 3
    prix_actuel: float
    prix_bas: float
    prix_central: float
    prix_haut: float
    unite: str
    tendance: Literal["hausse", "baisse", "stable"]
    metriques: dict[str, Any] = Field(default_factory=dict)
    importances: dict[str, float] = Field(default_factory=dict)
    scenarios: dict[str, dict[str, float]] = Field(default_factory=dict)
    part_donnees_proxy: float = Field(ge=0.0, le=1.0)
    limites: list[str] = Field(default_factory=list)