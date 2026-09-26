import unittest
from datetime import date, timedelta

from src.agents.feature_predictor_agent.agent import forecast_monthly_price, run
from src.schemas import (
    CollectorOutput,
    MarketDataPoint,
    MatierePremiereOutput,
    VariableOutput,
    WeatherNewsOutput,
)


def _run_with_prices(prices, *, synthetic=False, include_synthetic=False):
    start = date(2026, 9, 1)
    material = MatierePremiereOutput(
        matiere="aluminium",
        source="test_fixture",
        is_synthetic=synthetic,
        points=[
            MarketDataPoint(
                date=start + timedelta(days=index),
                prix_unitaire=price,
                quantite=1.0,
                valeur_importee=price,
                code_sh="7601",
            )
            for index, price in enumerate(prices)
        ],
    )
    return run(
        CollectorOutput(variables=[], matieres_premieres=[material]),
        WeatherNewsOutput(score_risque=0.4, events=[], zone="Tunisie"),
        include_synthetic=include_synthetic,
    )


class AluminiumPredictionTests(unittest.TestCase):
    def test_rising_prices_predict_upward_trend(self):
        result = _run_with_prices([100, 103, 106, 109, 112, 115, 118])

        self.assertEqual(len(result.predictions), 1)
        self.assertEqual(result.predictions[0].matiere, "aluminium")
        self.assertEqual(result.predictions[0].tendance, "hausse")
        self.assertGreater(result.predictions[0].confiance, 0.5)
        self.assertEqual(len(result.features), 7)
        self.assertEqual(result.features[-1].score_risque_meteo_news, 0.4)

    def test_falling_prices_predict_downward_trend(self):
        result = _run_with_prices([118, 115, 112, 109, 106, 103, 100])

        self.assertEqual(result.predictions[0].tendance, "baisse")

    def test_synthetic_or_missing_history_does_not_make_prediction(self):
        synthetic = _run_with_prices([100, 103, 106], synthetic=True)
        insufficient = _run_with_prices([100])

        self.assertEqual(synthetic.predictions, [])
        self.assertEqual(synthetic.features, [])
        self.assertEqual(insufficient.predictions, [])

    def test_demo_opt_in_returns_a_marked_synthetic_prediction(self):
        result = _run_with_prices(
            [100, 101, 103, 105, 107, 109, 112],
            synthetic=True,
            include_synthetic=True,
        )

        self.assertEqual(result.predictions[0].tendance, "hausse")
        self.assertTrue(result.predictions[0].is_synthetic)

    def test_monthly_forecast_uses_backtested_model_and_future_dates(self):
        prices = [100.0 + index for index in range(36)]
        points = []
        for index, price in enumerate(prices):
            month_number = 2023 * 12 + index
            year, month_index = divmod(month_number, 12)
            month = month_index + 1
            points.append(
                MarketDataPoint(
                    date=date(year, month, 1),
                    prix_unitaire=price,
                    quantite=0.0,
                    valeur_importee=0.0,
                    code_sh="GLOBAL",
                    type_donnee="benchmark",
                )
            )
        material = MatierePremiereOutput(
            matiere="aluminium",
            points=points,
            source="FRED PALUMUSDM",
            is_synthetic=False,
        )

        result = forecast_monthly_price(
            material, horizon_months=6, today=date(2025, 12, 1)
        )

        self.assertEqual(result.methode, "dernier_prix")
        self.assertEqual(result.dernier_prix, 135.0)
        self.assertEqual(result.observations_validation, 12)
        self.assertEqual(result.erreur_absolue_validation, 1.0)
        self.assertEqual(result.previsions[0].date, date(2026, 1, 1))
        self.assertEqual(result.previsions[-1].date, date(2026, 6, 1))
        self.assertEqual(result.previsions[0].prix_prevu, 135.0)
        self.assertLess(result.previsions[0].borne_basse, 135.0)
        self.assertGreater(result.previsions[0].borne_haute, 135.0)

    def test_monthly_forecast_rejects_synthetic_and_short_history(self):
        synthetic = MatierePremiereOutput(
            matiere="aluminium", points=[], source="demo", is_synthetic=True
        )
        short_history = MatierePremiereOutput(
            matiere="aluminium",
            points=[
                MarketDataPoint(
                    date=date(2026, month, 1),
                    prix_unitaire=100.0,
                    quantite=0.0,
                    valeur_importee=0.0,
                    code_sh="GLOBAL",
                )
                for month in range(1, 13)
            ],
            source="short fixture",
            is_synthetic=False,
        )

        with self.assertRaisesRegex(ValueError, "observations reelles"):
            forecast_monthly_price(synthetic)
        with self.assertRaisesRegex(ValueError, "au moins 36 mois"):
            forecast_monthly_price(short_history)


if __name__ == "__main__":
    unittest.main()