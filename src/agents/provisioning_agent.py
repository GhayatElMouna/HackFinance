from dataclasses import dataclass
from pathlib import Path

import pandas as pd


FAOSTAT_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "raw"
    / "faostat_food_balances_africa"
    / "FoodBalanceSheets_E_Africa.csv"
)


@dataclass(frozen=True)
class WheatDemandBaseline:
    year: int
    domestic_supply_tonnes: float
    food_use_tonnes: float
    production_tonnes: float
    import_tonnes: float
    source: str


@dataclass(frozen=True)
class ProvisioningPlan:
    reference_year: int
    planning_months: int
    buffer_days: int
    daily_demand_tonnes: float
    demand_over_horizon_tonnes: float
    target_buffer_tonnes: float
    stock_cover_days: float
    total_available_tonnes: float
    quantity_to_procure_tonnes: float


def load_latest_tunisia_wheat_baseline() -> WheatDemandBaseline:
    if not FAOSTAT_PATH.exists():
        raise FileNotFoundError(
            f"Bilan FAOSTAT absent: {FAOSTAT_PATH}. "
            "Telechargez FoodBalanceSheets_E_Africa.zip depuis FAOSTAT."
        )

    header = pd.read_csv(FAOSTAT_PATH, nrows=0).columns
    year_columns = sorted(
        (column for column in header if len(column) == 5 and column[1:].isdigit()),
        key=lambda column: int(column[1:]),
    )
    required_elements = {
        "Domestic supply quantity": "domestic_supply_tonnes",
        "Food": "food_use_tonnes",
        "Production": "production_tonnes",
        "Import quantity": "import_tonnes",
    }
    frame = pd.read_csv(
        FAOSTAT_PATH,
        usecols=["Area", "Item", "Element", "Unit", *year_columns],
    )
    frame = frame[
        (frame["Area"] == "Tunisia")
        & (frame["Item"] == "Wheat and products")
        & frame["Element"].isin(required_elements)
    ].set_index("Element")

    for year_column in reversed(year_columns):
        if not all(element in frame.index for element in required_elements):
            break
        values = {
            element: pd.to_numeric(frame.loc[element, year_column], errors="coerce")
            for element in required_elements
        }
        if all(pd.notna(value) for value in values.values()):
            year = int(year_column[1:])
            unit = str(frame.loc["Domestic supply quantity", "Unit"])
            multiplier = 1000 if unit == "1000 t" else 1
            return WheatDemandBaseline(
                year=year,
                domestic_supply_tonnes=float(values["Domestic supply quantity"] * multiplier),
                food_use_tonnes=float(values["Food"] * multiplier),
                production_tonnes=float(values["Production"] * multiplier),
                import_tonnes=float(values["Import quantity"] * multiplier),
                source="FAOSTAT Food Balances, Tunisia, Wheat and products",
            )

    raise ValueError("Aucune annee FAOSTAT complete trouvee pour le bilan du ble tunisien.")


def calculate_provisioning_plan(
    baseline: WheatDemandBaseline,
    planning_months: int,
    buffer_days: int,
    current_stocks_tonnes: float,
    scheduled_arrivals_tonnes: float,
    expected_harvest_tonnes: float,
) -> ProvisioningPlan:
    if not 1 <= planning_months <= 24:
        raise ValueError("L'horizon doit etre compris entre 1 et 24 mois.")
    if not 0 <= buffer_days <= 365:
        raise ValueError("Le stock tampon doit etre compris entre 0 et 365 jours.")
    quantities = (current_stocks_tonnes, scheduled_arrivals_tonnes, expected_harvest_tonnes)
    if any(quantity < 0 for quantity in quantities):
        raise ValueError("Les stocks, arrivees et recoltes doivent etre positifs ou nuls.")

    daily_demand = baseline.domestic_supply_tonnes / 365.25
    horizon_days = planning_months * 365.25 / 12
    horizon_demand = daily_demand * horizon_days
    target_buffer = daily_demand * buffer_days
    available = sum(quantities)
    required = max(0.0, horizon_demand + target_buffer - available)

    return ProvisioningPlan(
        reference_year=baseline.year,
        planning_months=planning_months,
        buffer_days=buffer_days,
        daily_demand_tonnes=daily_demand,
        demand_over_horizon_tonnes=horizon_demand,
        target_buffer_tonnes=target_buffer,
        stock_cover_days=current_stocks_tonnes / daily_demand if daily_demand else 0.0,
        total_available_tonnes=available,
        quantity_to_procure_tonnes=required,
    )
