"""
Contrat de donnees partage entre tous les agents.
Toute personne modifiant une structure ici doit prevenir l equipe
(referent : Explicateur/orchestration).
"""
from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


AgentStatusLiteral = Literal["idle", "running", "done", "error"]


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


# ---------- Agent Lois de Finances ----------

class BudgetLine(BaseModel):
    annee: int
    poste: str
    matiere: Optional[str] = None  # "petrole", "ble", ... ou None si transversal
    montant_mdt: float             # millions de dinars
    variation_pct: Optional[float] = None
    commentaire: str = ""


class FinanceLawYearSummary(BaseModel):
    annee: int
    source_document: str
    total_subventions_mdt: Optional[float] = None
    lignes: List[BudgetLine] = Field(default_factory=list)
    resume: str = ""


class FinanceLawOutput(BaseModel):
    annees_analysees: List[int]
    resumes_par_annee: List[FinanceLawYearSummary]
    tendances_par_matiere: Dict[str, str] = Field(default_factory=dict)
    features_budgetaires: Dict[str, float] = Field(default_factory=dict)
    # ex: pression_budgetaire_petrole, variation_3ans_ble, ...
    source_mode: str = "curated"  # curated | pdf | llm | hybrid
    warnings: List[str] = Field(default_factory=list)
    is_synthetic: bool = False


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
    prix_reference_usd_tonne: Optional[float] = None
    moyenne_mobile_3m: Optional[float] = None
    volatilite_3m: Optional[float] = None
    momentum_3m: Optional[float] = None
    variation_fx: Optional[float] = None
    score_risque_meteo_news: Optional[float] = None
    brent_usd_baril: Optional[float] = None
    uree_usd_tonne: Optional[float] = None
    moyenne_mobile_7j: Optional[float] = None
    volatilite_glissante: Optional[float] = None
    momentum: Optional[float] = None
    # Facteurs issus de l'Agent Lois de Finances
    depense_budget_mdt: Optional[float] = None
    variation_budget_pct: Optional[float] = None
    score_pression_budgetaire: Optional[float] = None


class PredictionOutput(BaseModel):
    matiere: str
    tendance: str               # "hausse" | "baisse" | "stable_volatile"
    confiance: float            # 0 a 1
    is_synthetic: bool = False
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
    modele: str = "baseline_momentum"
    comparaison_modeles: dict[str, dict[str, float]] = Field(default_factory=dict)
    sensibilites_facteurs: dict[str, float] = Field(default_factory=dict)
    sensibilites_observations: dict[str, int] = Field(default_factory=dict)
    budget_a_influence: bool = False


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
    budget_mentionne: bool = False


class PipelineResult(BaseModel):
    collector: CollectorOutput
    weather_news: WeatherNewsOutput
    lois_finances: Optional[FinanceLawOutput] = None
    feature_predictor: FeaturePredictorOutput
    explanations: List[ExplainerOutput]
    agent_status: Dict[str, AgentStatusLiteral] = Field(default_factory=dict)
