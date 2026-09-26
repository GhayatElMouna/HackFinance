import unittest
from unittest.mock import patch

from src.agents.collector_agent import agent as collector_agent
from src.schemas import MatierePremiereOutput, VariableOutput


class CollectorLiveAgentTests(unittest.TestCase):
    @patch("src.agents.collector_agent.agent.prix_international_agent.run")
    @patch("src.agents.collector_agent.agent.brent_agent.run")
    @patch("src.agents.collector_agent.agent.usd_tnd_agent.run")
    @patch("src.agents.collector_agent.agent.inflation_agent.run")
    @patch("src.agents.collector_agent.agent.aluminium_agent.run")
    def test_parent_keeps_live_results_and_reports_failed_sources(
        self, aluminium, inflation, fx, brent, international
    ):
        international.side_effect = RuntimeError("FRED unavailable")
        brent.return_value = VariableOutput(
            nom="brent", date="2026-09-24", valeur=72.0,
            unite="USD/baril", source="FRED", is_synthetic=False,
        )
        fx.return_value = VariableOutput(
            nom="usd_tnd", date="2025-01-01", valeur=3.1,
            unite="TND/USD", source="World Bank", is_synthetic=False,
        )
        inflation.return_value = VariableOutput(
            nom="inflation", date="2025-01-01", valeur=5.0,
            unite="%", source="World Bank", is_synthetic=False,
        )
        aluminium.return_value = MatierePremiereOutput(
            matiere="aluminium", points=[], source="FRED", is_synthetic=False
        )

        result = collector_agent.run(["aluminium", "plastiques"])

        self.assertEqual([item.nom for item in result.variables], ["brent", "usd_tnd", "inflation"])
        self.assertEqual(result.matieres_premieres[0].matiere, "aluminium")
        self.assertTrue(any("prix_international" in error for error in result.collection_errors))
        self.assertTrue(any("plastiques" in error for error in result.collection_errors))


if __name__ == "__main__":
    unittest.main()