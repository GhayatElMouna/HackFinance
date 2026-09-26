import unittest

from src.agents.feature_predictor_agent.agent import _select_direction_model


class DirectionModelSelectionTests(unittest.TestCase):
    def test_direction_accuracy_takes_priority_over_price_error(self):
        metrics = {
            "prophet": {"directional_accuracy": 0.45, "mape_pct": 3.0},
            "momentum3": {"directional_accuracy": 0.54, "mape_pct": 8.0},
        }

        self.assertEqual(_select_direction_model(metrics), "momentum3")

    def test_mape_breaks_direction_accuracy_tie(self):
        metrics = {
            "prophet": {"directional_accuracy": 0.5, "mape_pct": 9.0},
            "momentum3": {"directional_accuracy": 0.5, "mape_pct": 6.0},
        }

        self.assertEqual(_select_direction_model(metrics), "momentum3")


if __name__ == "__main__":
    unittest.main()