from __future__ import annotations

from datetime import date, timedelta

from src.schemas import ExplainerOutput, FeaturePredictorOutput


TREND_LABELS = {
    "hausse": "une hausse recente",
    "baisse": "une baisse recente",
    "stable_volatile": "une evolution plutot stable ou volatile",
}


def _format_number(value: float, decimals: int = 2) -> str:
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def _explain_one(
    matiere: str,
    prediction,
    features,
    forecast,
) -> ExplainerOutput:
    latest_feature = max(features, key=lambda feature: feature.date) if features else None
    importance = {}
    sentences = []
    is_stale = False
    if latest_feature is not None:
        staleness_days = 45 if matiere == "petrole" else 120
        is_stale = date.today() - latest_feature.date > timedelta(days=staleness_days)

    if prediction is not None:
        label = TREND_LABELS.get(prediction.tendance, prediction.tendance)
        if prediction.is_synthetic:
            sentences.append(
                f"La simulation indique {label}; ce resultat repose sur des donnees fictives. "
                f"Le score de soutien ({_format_number(prediction.confiance * 100, 1)}%) "
                "n'est pas une probabilite de reussite."
            )
        else:
            confidence_percent = _format_number(prediction.confiance * 100, 1)
            freshness = "L'historique disponible, ancien, indiquait " if is_stale else "Les derniers cours indiquent "
            sentences.append(
                f"{freshness}{label}. Le score de soutien est {confidence_percent}%; "
                "ce n'est pas une probabilite de reussite."
            )

    if latest_feature is not None:
        momentum = latest_feature.momentum
        volatility = latest_feature.volatilite_glissante
        total = abs(momentum) + abs(volatility)
        if total > 0:
            importance = {
                "momentum_prix_indicatif_pct": round(abs(momentum) / total * 100, 1),
                "volatilite_indicative_pct": round(abs(volatility) / total * 100, 1),
            }
        else:
            importance = {
                "momentum_prix_indicatif_pct": 50.0,
                "volatilite_indicative_pct": 50.0,
            }
        direction = "positif" if momentum > 0 else "negatif" if momentum < 0 else "nul"
        sentences.append(
            f"Au {latest_feature.date.isoformat()}, le momentum sur la fenetre observee "
            f"est {_format_number(momentum * 100, 2)}% ({direction}); la volatilite "
            f"des rendements est {_format_number(volatility * 100)}%."
        )
        if is_stale:
            sentences.append(
                "Ces chiffres sont historiques et trop anciens pour decrire le prix actuel; "
                "aucune prevision future n'est publiee pour cette serie."
            )
        sentences.append(
            "Le change et la meteo sont affiches comme variables de contexte, mais "
            "ne sont pas encore utilises pour calculer cette direction."
        )

    if forecast is not None:
        final_point = forecast.previsions[-1]
        method = {
            "dernier_prix": "reconduction du dernier prix observe",
            "moyenne_3_mois": "moyenne des trois derniers mois",
        }.get(forecast.methode, forecast.methode)
        sentences.append(
            f"Prevision de prix ({forecast.source}): dernier cours "
            f"{_format_number(forecast.dernier_prix)} "
            f"{forecast.unite} au {forecast.derniere_observation.isoformat()}; "
            f"methode retenue: {method}. A {forecast.horizon_mois} mois "
            f"({final_point.date.isoformat()}), le prix central est "
            f"{_format_number(final_point.prix_prevu)} {forecast.unite}, avec une plage "
            f"empirique [{_format_number(final_point.borne_basse)}; "
            f"{_format_number(final_point.borne_haute)}]."
        )
        sentences.append(
            f"Sur le test final de {forecast.observations_validation} mois, "
            f"MAE = {_format_number(forecast.erreur_absolue_validation)} {forecast.unite} "
            f"et MAPE = {_format_number(forecast.erreur_relative_validation_pct)}%. "
            "Cette plage est fondee sur les erreurs passees; ce n'est pas un intervalle "
            "de confiance ni une garantie."
        )
    elif prediction is None:
        sentences.append(
            "Aucune explication predictive disponible: historique reel insuffisant."
        )

    return ExplainerOutput(
        matiere=matiere,
        texte_explicatif=" ".join(sentences),
        feature_importances=importance,
    )
from src.schemas import FeaturePredictorOutput, ExplainerOutput


def run(feature_predictor: FeaturePredictorOutput) -> list[ExplainerOutput]:
    """Explain observed direction and validated future-price forecasts."""
    predictions = {item.matiere: item for item in feature_predictor.predictions}
    forecasts = {item.matiere: item for item in feature_predictor.price_forecasts}
    features_by_material = {}
    for feature in feature_predictor.features:
        features_by_material.setdefault(feature.matiere, []).append(feature)

    materials = dict.fromkeys(
        [*predictions, *forecasts, *features_by_material]
    )
    return [
        _explain_one(
            matiere,
            predictions.get(matiere),
            features_by_material.get(matiere, []),
            forecasts.get(matiere),
        )
        for matiere in materials
    ]
