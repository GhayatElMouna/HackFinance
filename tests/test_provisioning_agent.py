import unittest
from datetime import date
from unittest.mock import patch

from src.agents.provisioning_agent.agent import run, run_with_web_price
from src.schemas import ProvisioningRequest


class ProvisioningAgentTests(unittest.TestCase):
    def test_low_coverage_recommends_urgent_replenishment(self):
        result = run(
            ProvisioningRequest(
                matiere="aluminium",
                stock_disponible_t=8,
                consommation_journaliere_t=1,
                delai_approvisionnement_jours=10,
                stock_securite_jours=5,
                quantite_en_transit_t=2,
                prix_unitaire_tnd_t=8000,
            ),
            today=date(2026, 9, 26),
        )

        self.assertEqual(result.niveau_urgence, "urgent")
        self.assertEqual(result.couverture_jours, 10)
        self.assertEqual(result.seuil_declenchement_t, 15)
        self.assertEqual(result.quantite_a_commander_t, 5)
        self.assertEqual(result.date_commande_recommandee, date(2026, 9, 26))
        self.assertEqual(result.cout_estime_tnd, 40000)

    def test_stock_above_reorder_threshold_needs_no_order(self):
        result = run(
            ProvisioningRequest(
                stock_disponible_t=20,
                consommation_journaliere_t=1,
                delai_approvisionnement_jours=10,
                stock_securite_jours=5,
            )
        )

        self.assertEqual(result.niveau_urgence, "aucun_besoin")
        self.assertEqual(result.quantite_a_commander_t, 0)
        self.assertIsNone(result.date_commande_recommandee)

    def test_invalid_consumption_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "consommation journaliere"):
            run(
                ProvisioningRequest(
                    stock_disponible_t=20,
                    consommation_journaliere_t=0,
                    delai_approvisionnement_jours=10,
                )
            )

    @patch(
        "src.agents.provisioning_agent.agent.latest_aluminium_price_tnd_t",
        return_value=(date(2026, 7, 1), 10000.0, "FRED x World Bank (2025)"),
    )
    def test_missing_manual_price_uses_live_reference_and_keeps_provenance(self, _mock_quote):
        result = run_with_web_price(
            ProvisioningRequest(
                stock_disponible_t=5,
                consommation_journaliere_t=1,
                delai_approvisionnement_jours=5,
                stock_securite_jours=5,
            ),
            today=date(2026, 9, 26),
        )

        self.assertEqual(result.cout_estime_tnd, 50000)
        self.assertEqual(result.source_prix, "FRED x World Bank (2025)")
        self.assertEqual(result.date_prix, date(2026, 7, 1))


if __name__ == "__main__":
    unittest.main()