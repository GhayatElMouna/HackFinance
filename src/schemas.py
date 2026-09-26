"""
Contrat de donnees partage entre tous les agents.
Toute personne modifiant une structure ici doit prevenir l equipe
(referent : Explicateur/orchestration).
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date


# ---------- Sous-agents Variables ----------

class VariableOutput(BaseModel):
    nom: str                 # "prix_international", "brent", "usd_tnd", "inflation"
    date: date
    valeur: float
    unite: str                # ex: "$/baril", "TND", "%"
    source: str
    is_synthetic: bool = False


# ---------- Sous-agents Matieres Premieres ----------

class MarketDataPoint(BaseModel):
    date: date
    code_sh: str
    prix_unitaire: Optional[float] = None
    quantite: Optional[float] = None
    valeur_importee: Optional[float] = None
    pays_origine: Optional[str] = None
    prix_reference_usd_tonne: Optional[float] = None
    brent_usd_baril: Optional[float] = None
    uree_usd_tonne: Optional[float] = None


class MatierePremiereOutput(BaseModel):
    matiere: str               # "ble", "petrole", "plastiques", "aluminium"
    points: List[MarketDataPoint]
    source: str
    is_synthetic: bool = False


# ---------- Agent Collecteur (parent, agrege les deux branches) ----------

class CollectorOutput(BaseModel):
    variables: List[VariableOutput]
    matieres_premieres: List[MatierePremiereOutput]


# ---------- Agent Meteo/News ----------

class NewsEvent(BaseModel):
    date: date
    titre: str
    score_impact: float        # -1 (baissier) a +1 (haussier)


class WeatherNewsOutput(BaseModel):
    score_risque: float        # 0 a 1, agrege
    events: List[NewsEvent]
    zone: str


# ---------- Agent Feature Engineer + Predicteur ----------

class FeatureRow(BaseModel):
    date: date
    matiere: str
    prix_reference_usd_tonne: float
    moyenne_mobile_3m: float
    volatilite_3m: float
    momentum_3m: float
    variation_fx: Optional[float] = None
    score_risque_meteo_news: Optional[float] = None
    brent_usd_baril: Optional[float] = None
    uree_usd_tonne: Optional[float] = None


class PredictionOutput(BaseModel):
    matiere: str
    tendance: str               # "hausse" | "baisse" | "stable_volatile"
    confiance: float            # 0 a 1
    prix_prevu: Optional[float] = None
    unite: Optional[str] = None
    horizon_mois: int = 1
    date_cible: Optional[date] = None
    precision_historique: Optional[float] = None
    observations_selection: int = 0
    mape_validation_pct: Optional[float] = None
    mape_baseline_validation_pct: Optional[float] = None
    observations_validation: int = 0
    source: Optional[str] = None
    prix_bas: Optional[float] = None
    prix_haut: Optional[float] = None
    prix_prophet: Optional[float] = None
    modele: str = "Prophet"
    comparaison_modeles: dict[str, dict[str, float]] = Field(default_factory=dict)
    sensibilites_facteurs: dict[str, float] = Field(default_factory=dict)
    sensibilites_observations: dict[str, int] = Field(default_factory=dict)


class FeaturePredictorOutput(BaseModel):
    features: List[FeatureRow]
    predictions: List[PredictionOutput]


# ---------- Agent Explicateur + orchestration ----------

class ExplainerOutput(BaseModel):
    matiere: str
    texte_explicatif: str
    feature_importances: dict   # {nom_feature: importance}


class PipelineResult(BaseModel):
    collector: CollectorOutput
    weather_news: WeatherNewsOutput
    feature_predictor: FeaturePredictorOutput
    explanations: List[ExplainerOutput]
