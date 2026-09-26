import unittest
from datetime import date

from src.agents.explainer_orchestrator_agent.agent import run
from src.schemas import (
    FeaturePredictorOutput,
    FeatureRow,
    PredictionOutput,
    PriceForecastOutput,
    PriceForecastPoint,
)


class ExplainerAgentTests(unittest.TestCase):
    def test_explains_real_trend_forecast_metrics_and_limits(self):
        output = FeaturePredictorOutput(
            features=[
                FeatureRow(
                    date=date(2026, 7, 1),
                    matiere="aluminium",
                    moyenne_mobile_7j=3100,
                    volatilite_glissante=0.03,
                    momentum=-0.04,
                    variation_fx=0.0,
                    score_risque_meteo_news=0.2,
                )
            ],
            predictions=[
                PredictionOutput(
                    matiere="aluminium",
                    tendance="baisse",
                    confiance=0.6,
                )
            ],
            price_forecasts=[
                PriceForecastOutput(
                    matiere="aluminium",
                    source="FRED PALUMUSDM",
                    unite="USD/tonne",
                    derniere_observation=date(2026, 7, 1),
                    dernier_prix=3158.26,
                    methode="dernier_prix",
                    horizon_mois=6,
                    erreur_absolue_validation=142.06,
                    erreur_relative_validation_pct=4.42,
                    observations_validation=12,
                    previsions=[
                        PriceForecastPoint(
                            date=date(2027, 1, 1),
                            prix_prevu=3158.26,
                            borne_basse=2904.25,
                            borne_haute=3412.28,
                        )
                    ],
                )
            ],
        )

        explanations = run(output)

        self.assertEqual(len(explanations), 1)
        explanation = explanations[0]
        self.assertEqual(explanation.matiere, "aluminium")
        self.assertNotIn("TODO", explanation.texte_explicatif)
        self.assertIn("baisse recente", explanation.texte_explicatif)
        self.assertIn("3 158,26 USD/tonne", explanation.texte_explicatif)
        self.assertIn("MAE = 142,06 USD/tonne", explanation.texte_explicatif)
        self.assertIn("pas un intervalle de confiance", explanation.texte_explicatif)
        self.assertAlmostEqual(
            sum(explanation.feature_importances.values()), 100.0
        )

    def test_synthetic_prediction_is_identified_as_simulation(self):
        explanations = run(
            FeaturePredictorOutput(
                features=[],
                predictions=[
                    PredictionOutput(
                        matiere="aluminium",
                        tendance="hausse",
                        confiance=1.0,
                        is_synthetic=True,
                    )
                ],
            )
        )

        self.assertIn("donnees fictives", explanations[0].texte_explicatif)
        self.assertIn("pas une probabilite", explanations[0].texte_explicatif)

    def test_old_history_is_described_as_historical_not_current(self):
        explanations = run(
            FeaturePredictorOutput(
                features=[
                    FeatureRow(
                        date=date(2024, 12, 1),
                        matiere="ble",
                        moyenne_mobile_7j=250,
                        volatilite_glissante=0.02,
                        momentum=-0.03,
                        variation_fx=0,
                        score_risque_meteo_news=0,
                    )
                ],
                predictions=[
                    PredictionOutput(
                        matiere="ble", tendance="baisse", confiance=0.6
                    )
                ],
            )
        )

        self.assertIn("historique disponible, ancien", explanations[0].texte_explicatif)
        self.assertIn("trop anciens", explanations[0].texte_explicatif)
        self.assertIn("aucune prevision future", explanations[0].texte_explicatif)


if __name__ == "__main__":
    unittest.main()