import unittest

import pandas as pd

from src.agents.collector_agent.official_sources import (
    collect_fred_aluminium,
    collect_imf_pcps,
    filter_wb_aluminium,
    latest_fred_observation,
    latest_wb_observation,
)


class FakeResponse:
    text = (
        "TIME_PERIOD,COMMODITY_CODE,OBS_VALUE\n"
        "2024-M01,PALUM,2250.5\n"
        "2024-M01,PCOPP,8300.0\n"
    )
    content = text.encode("utf-8")


class FakeCollector:
    def __init__(self):
        self.url = ""

    def get(self, url):
        self.url = url
        return FakeResponse()

    def save_raw(self, content, name, suffix):
        return None


class AluminiumSourceTests(unittest.TestCase):
    def test_imf_collection_requests_only_aluminum(self):
        collector = FakeCollector()

        frame = collect_imf_pcps(
            collector, commodity_codes=["PALUM"]
        )

        self.assertIn("M.W00.PALUM.USD", collector.url)
        self.assertEqual(frame["series"].tolist(), ["aluminum"])
        self.assertEqual(frame["value"].tolist(), [2250.5])

    def test_pinksheet_filter_excludes_other_commodities(self):
        frame = pd.DataFrame(
            {
                "period": ["2024M01", "2024M01", "2024M01"],
                "series_raw": ["Aluminum", "Copper", "Aluminium alloy"],
                "value": [2250.5, 8300.0, 2200.0],
            }
        )

        result = filter_wb_aluminium(frame)

        self.assertEqual(result["series_raw"].tolist(), ["Aluminum", "Aluminium alloy"])
        self.assertEqual(result["series"].tolist(), ["aluminum", "aluminum"])

    def test_fred_collector_normalizes_monthly_usd_prices(self):
        class FredCollector(FakeCollector):
            def get(self, url):
                self.url = url
                return type(
                    "Response",
                    (),
                    {
                        "text": (
                            "observation_date,PALUMUSDM\n"
                            "2026-06-01,3438.84\n"
                            "2026-07-01,3158.26\n"
                            "2026-08-01,.\n"
                        ),
                        "content": b"test CSV",
                    },
                )()

        collector = FredCollector()
        result = collect_fred_aluminium(collector)

        self.assertIn("PALUMUSDM", collector.url)
        self.assertEqual(result["period"].tolist(), ["2026-06", "2026-07"])
        self.assertEqual(result["unit"].unique().tolist(), ["USD/mt"])
        self.assertEqual(result["value"].tolist(), [3438.84, 3158.26])

    def test_latest_fred_observation_ignores_missing_values(self):
        class LatestFredCollector(FakeCollector):
            def get(self, url):
                return type(
                    "Response",
                    (),
                    {
                        "text": (
                            "observation_date,DCOILBRENTEU\n"
                            "2026-09-22,70.5\n"
                            "2026-09-23,.\n"
                            "2026-09-24,72.0\n"
                        ),
                        "content": b"test",
                    },
                )()

        observed_on, value = latest_fred_observation(
            LatestFredCollector(), "DCOILBRENTEU"
        )

        self.assertEqual(str(observed_on), "2026-09-24")
        self.assertEqual(value, 72.0)

    def test_latest_world_bank_observation_selects_latest_non_null_year(self):
        class LatestWBCollector(FakeCollector):
            def get(self, url, **kwargs):
                return type(
                    "Response",
                    (),
                    {
                        "json": lambda self: [
                            {"pages": 1},
                            [
                                {"date": "2023", "value": 3.2},
                                {"date": "2025", "value": None},
                                {"date": "2024", "value": 3.1},
                            ],
                        ]
                    },
                )()

        observed_on, value = latest_wb_observation(
            LatestWBCollector(), "PA.NUS.FCRF"
        )

        self.assertEqual(str(observed_on), "2024-01-01")
        self.assertEqual(value, 3.1)


if __name__ == "__main__":
    unittest.main()