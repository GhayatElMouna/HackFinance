import unittest
from unittest.mock import patch

from src.agents.weather_news_agent.agent import run


class FakeCollector:
    def get(self, url, **kwargs):
        if "geocoding" in url:
            return type(
                "Response",
                (),
                {
                    "json": lambda self: {
                        "results": [{"name": "Bizerte", "latitude": 37.27, "longitude": 9.87}]
                    }
                },
            )()
        return type(
            "Response",
            (),
            {
                "json": lambda self: {
                    "daily": {
                        "time": ["2026-09-26", "2026-09-27"],
                        "precipitation_sum": [5.0, 30.0],
                        "wind_speed_10m_max": [20.0, 55.0],
                        "temperature_2m_max": [29.0, 32.0],
                    }
                }
            },
        )()


class WeatherAgentTests(unittest.TestCase):
    @patch.dict("os.environ", {"NEWS_API_KEY": ""}, clear=False)
    @patch("src.agents.weather_news_agent.agent.Collector", FakeCollector)
    def test_fetches_forecast_and_reports_weather_risk(self):
        result = run("zones cerealieres nord Tunisie", matieres=["petrole"])

        self.assertEqual(result.zone, "Bizerte, Tunisie")
        self.assertEqual(result.score_risque, 0.6)
        self.assertEqual(len(result.events), 1)
        self.assertIn("Open-Meteo", result.source)
        self.assertFalse(result.is_synthetic)
        self.assertTrue(
            any("NEWS_API_KEY" in error for error in result.collection_errors)
        )


if __name__ == "__main__":
    unittest.main()
