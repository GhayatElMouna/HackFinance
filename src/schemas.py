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
    prix_unitaire: float      # valeur / quantite
    quantite: float
    valeur_importee: float
    code_sh: str
    pays_origine: Optional[str] = None
    type_donnee: str = "import"


class MatierePremiereOutput(BaseModel):
    matiere: str               # "ble", "petrole", "plastiques", "aluminium"
    points: List[MarketDataPoint]
    source: str
    is_synthetic: bool = False


# ---------- Agent Collecteur (parent, agrege les deux branches) ----------

class CollectorOutput(BaseModel):
    variables: List[VariableOutput]
    matieres_premieres: List[MatierePremiereOutput]
    collection_errors: List[str] = Field(default_factory=list)


# ---------- Agent Meteo/News ----------

class NewsEvent(BaseModel):
    date: date
    titre: str
    score_impact: float        # -1 (baissier) a +1 (haussier)


class WeatherNewsOutput(BaseModel):
    score_risque: float        # 0 a 1, agrege
    events: List[NewsEvent]
    zone: str
    source: str = "unknown"
    is_synthetic: bool = False
    collection_errors: List[str] = Field(default_factory=list)


# ---------- Agent Feature Engineer + Predicteur ----------

class FeatureRow(BaseModel):
    date: date
    matiere: str
    moyenne_mobile_7j: float
    volatilite_glissante: float
    momentum: float
    variation_fx: float
    score_risque_meteo_news: float


class PredictionOutput(BaseModel):
    matiere: str
    tendance: str               # "hausse" | "baisse" | "stable_volatile"
    confiance: float            # 0 a 1
    is_synthetic: bool = False


class PriceForecastPoint(BaseModel):
    date: date
    prix_prevu: float
    borne_basse: float
    borne_haute: float


class PriceForecastOutput(BaseModel):
    matiere: str
    source: str
    unite: str
    derniere_observation: date
    dernier_prix: float
    methode: str
    horizon_mois: int
    erreur_absolue_validation: float
    erreur_relative_validation_pct: float
    observations_validation: int
    previsions: List[PriceForecastPoint]


class FeaturePredictorOutput(BaseModel):
    features: List[FeatureRow]
    predictions: List[PredictionOutput]
    price_forecasts: List[PriceForecastOutput] = Field(default_factory=list)


# ---------- Agent de provisionnement ----------

class ProvisioningRequest(BaseModel):
    matiere: str = "aluminium"
    stock_disponible_t: float
    consommation_journaliere_t: float
    delai_approvisionnement_jours: int
    stock_securite_jours: int = 14
    quantite_en_transit_t: float = 0.0
    prix_unitaire_tnd_t: Optional[float] = None


class ProvisioningOutput(BaseModel):
    matiere: str
    couverture_jours: float
    seuil_declenchement_t: float
    quantite_a_commander_t: float
    niveau_urgence: str
    date_commande_recommandee: Optional[date] = None
    cout_estime_tnd: Optional[float] = None
    source_prix: Optional[str] = None
    date_prix: Optional[date] = None
    justification: str


# ---------- Agent Explicateur + orchestration ----------

class ExplainerOutput(BaseModel):
    matiere: str
    texte_explicatif: str
    feature_importances: dict   # poids indicatifs, pas des valeurs SHAP


class PipelineResult(BaseModel):
    collector: CollectorOutput
    weather_news: WeatherNewsOutput
    feature_predictor: FeaturePredictorOutput
    explanations: List[ExplainerOutput]
