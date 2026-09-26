import unittest

from src.agents.provisioning_agent import (
    WheatDemandBaseline,
    calculate_provisioning_plan,
)


class ProvisioningPlanTests(unittest.TestCase):
    def setUp(self):
        self.baseline = WheatDemandBaseline(
            year=2023,
            domestic_supply_tonnes=365_250,
            food_use_tonnes=250_000,
            production_tonnes=100_000,
            import_tonnes=200_000,
            source="test",
        )

    def test_calculates_horizon_demand_buffer_and_gap(self):
        plan = calculate_provisioning_plan(
            self.baseline,
            planning_months=3,
            buffer_days=30,
            current_stocks_tonnes=20_000,
            scheduled_arrivals_tonnes=10_000,
            expected_harvest_tonnes=5_000,
        )

        self.assertAlmostEqual(plan.daily_demand_tonnes, 1_000)
        self.assertAlmostEqual(plan.demand_over_horizon_tonnes, 91_312.5)
        self.assertAlmostEqual(plan.target_buffer_tonnes, 30_000)
        self.assertAlmostEqual(plan.quantity_to_procure_tonnes, 86_312.5)

    def test_procurement_never_goes_below_zero(self):
        plan = calculate_provisioning_plan(
            self.baseline,
            planning_months=1,
            buffer_days=0,
            current_stocks_tonnes=50_000,
            scheduled_arrivals_tonnes=0,
            expected_harvest_tonnes=0,
        )

        self.assertEqual(plan.quantity_to_procure_tonnes, 0)


if __name__ == "__main__":
    unittest.main()