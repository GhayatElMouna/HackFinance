"""
Contrat de donnees partage entre tous les agents.
Toute personne modifiant une structure ici doit prevenir l equipe
(referent : Explicateur/orchestration).
"""
from pydantic import BaseModel
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
    prix_unitaire: float      # valeur / quantite
    quantite: float
    valeur_importee: float
    code_sh: str
    pays_origine: Optional[str] = None


class MatierePremiereOutput(BaseModel):
    matiere: str               # "ble", "petrole", "plastiques", "aluminium", "fer_acier"
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
    moyenne_mobile_7j: float
    volatilite_glissante: float
    momentum: float
    variation_fx: float
    score_risque_meteo_news: float


class ForecastPoint(BaseModel):
    date: date
    yhat: float
    yhat_lower: Optional[float] = None
    yhat_upper: Optional[float] = None


class PredictionOutput(BaseModel):
    matiere: str
    tendance: str               # "hausse" | "baisse" | "stable_volatile"
    confiance: float            # 0 a 1
    modele: str = "stub"        # "sarimax" | "xgboost" | "stub"
    variation_prevue_pct: float = 0.0
    attributs: dict = {}        # indicateurs + exogenes (valeurs numeriques)
    historique: List[ForecastPoint] = []
    forecast: List[ForecastPoint] = []


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
