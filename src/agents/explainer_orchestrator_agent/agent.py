import csv
import os
from datetime import date
from math import isfinite
from pathlib import Path
from statistics import median

from src.schemas import (
    FeaturePredictorOutput,
    ExplainerOutput,
    GasoilForecastOutput,
    GasoilScenario,
)


DEFAULT_DATASET = Path(
    os.environ.get(
        "GASOIL_FORECAST_DATASET",
        r"E:\Downloads\gasoil_forecasting_dataset.csv",
    )
)
REQUIRED_COLUMNS = ("date", "brent_usd_bbl", "ulsd_usd_gal", "crack_spread_usd_bbl")


def run(feature_predictor: FeaturePredictorOutput) -> list[ExplainerOutput]:
    """Point d entree de l agent Explicateur."""
    # TODO: calculer SHAP par matiere, generer le texte explicatif
    return [
        ExplainerOutput(matiere=p.matiere, texte_explicatif="TODO", feature_importances={})
        for p in feature_predictor.predictions
    ]


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _load_observations(dataset_path: Path) -> list[dict[str, float | date]]:
    with dataset_path.open("r", newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        missing_columns = set(REQUIRED_COLUMNS) - set(reader.fieldnames or [])
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"Dataset is missing required columns: {missing}")

        observations: list[dict[str, float | date]] = []
        for row_number, row in enumerate(reader, start=2):
            try:
                observation: dict[str, float | date] = {
                    "date": date.fromisoformat(row["date"]),
                    "brent_usd_bbl": float(row["brent_usd_bbl"]),
                    "ulsd_usd_gal": float(row["ulsd_usd_gal"]),
                    "crack_spread_usd_bbl": float(row["crack_spread_usd_bbl"]),
                }
            except (TypeError, ValueError) as error:
                raise ValueError(f"Invalid or missing value on CSV row {row_number}") from error

            if not all(
                isfinite(value)
                for key, value in observation.items()
                if key != "date"
            ):
                raise ValueError(f"Non-finite numeric value on CSV row {row_number}")
            if observation["ulsd_usd_gal"] <= 0:
                raise ValueError(f"ULSD price must be positive on CSV row {row_number}")
            observations.append(observation)

    observations.sort(key=lambda item: item["date"])
    if len(observations) < 7:
        raise ValueError("At least 7 complete monthly observations are required")
    dates = [item["date"] for item in observations]
    if len(set(dates)) != len(dates):
        raise ValueError("Dataset contains duplicate monthly dates")
    if any(_next_month(previous) != current for previous, current in zip(dates, dates[1:])):
        raise ValueError("Dataset must contain consecutive monthly observations")
    return observations


def run_gasoil_forecast(
    dataset_path: str | Path | None = None,
    brent_shock_pct: float = 10.0,
    crack_spread_shock_pct: float = 15.0,
) -> GasoilForecastOutput:
    """Build next-month ULSD scenarios from recent Brent and crack-spread changes."""
    if not 0 <= brent_shock_pct <= 100 or not 0 <= crack_spread_shock_pct <= 100:
        raise ValueError("Scenario shocks must be between 0 and 100 percent")

    path = Path(dataset_path) if dataset_path is not None else DEFAULT_DATASET
    observations = _load_observations(path)
    latest = observations[-1]
    recent = observations[-7:]

    brent_changes = [
        float(current["brent_usd_bbl"]) - float(previous["brent_usd_bbl"])
        for previous, current in zip(recent, recent[1:])
    ]
    spread_changes = [
        float(current["crack_spread_usd_bbl"]) - float(previous["crack_spread_usd_bbl"])
        for previous, current in zip(recent, recent[1:])
    ]
    baseline_brent = max(0.0, float(latest["brent_usd_bbl"]) + median(brent_changes))
    baseline_spread = float(latest["crack_spread_usd_bbl"]) + median(spread_changes)
    latest_price = float(latest["ulsd_usd_gal"])
    latest_brent = float(latest["brent_usd_bbl"])
    latest_spread = float(latest["crack_spread_usd_bbl"])

    spread_stress = max(abs(baseline_spread), 1.0) * crack_spread_shock_pct / 100
    definitions = (
        ("Baissier", baseline_brent * (1 - brent_shock_pct / 100), baseline_spread - spread_stress),
        ("Central", baseline_brent, baseline_spread),
        ("Haussier", baseline_brent * (1 + brent_shock_pct / 100), baseline_spread + spread_stress),
    )
    scenarios = []
    for name, scenario_brent, scenario_spread in definitions:
        projected_price = max(0.0, (scenario_brent + scenario_spread) / 42)
        brent_contribution = (scenario_brent - latest_brent) / 42
        spread_contribution = (scenario_spread - latest_spread) / 42
        change_pct = (projected_price / latest_price - 1) * 100
        direction = "augmenter" if projected_price > latest_price else "baisser"
        explanation = (
            f"Le prix de l'ULSD devrait {direction} de {abs(change_pct):.1f} % par rapport "
            f"a la derniere observation. Le Brent contribue pour "
            f"{brent_contribution:+.3f} USD/gallon et le crack spread pour "
            f"{spread_contribution:+.3f} USD/gallon. Une contribution positive pousse "
            "le prix a la hausse; une contribution negative le pousse a la baisse."
        )
        scenarios.append(
            GasoilScenario(
                nom=name,
                brent_usd_bbl=scenario_brent,
                crack_spread_usd_bbl=scenario_spread,
                prix_ulsd_usd_gal=projected_price,
                variation_vs_dernier_pct=change_pct,
                contribution_brent_usd_gal=brent_contribution,
                contribution_spread_usd_gal=spread_contribution,
                explication=explanation,
            )
        )

    return GasoilForecastOutput(
        matiere="gasoil / ULSD",
        date_derniere_observation=latest["date"],
        date_prevision=_next_month(latest["date"]),
        dernier_prix_ulsd_usd_gal=latest_price,
        scenarios=scenarios,
        methode=(
            "La prevision de base prolonge la mediane des six dernieres variations "
            "mensuelles du Brent et du crack spread. Le prix ULSD est estime par "
            "(Brent + crack spread) / 42 gallons par baril."
        ),
        avertissement=(
            "Cette estimation concerne le prix international de l'ULSD en USD/gallon, "
            "pas le prix a la pompe en Tunisie. Les cas baissier et haussier sont des "
            "scenarios de stress, pas des probabilites."
        ),
    )


def run_gasoil_simulation(
    dataset_path: str | Path | None = None,
    brent_change_pct: float = 0.0,
    crack_spread_change_pct: float = 0.0,
) -> GasoilScenario:
    """Simulate a user-defined change from the central next-month forecast."""
    if not -100 <= brent_change_pct <= 100:
        raise ValueError("La variation du Brent doit etre comprise entre -100 et 100 %")
    if not -100 <= crack_spread_change_pct <= 100:
        raise ValueError("La variation du crack spread doit etre comprise entre -100 et 100 %")

    forecast = run_gasoil_forecast(dataset_path)
    central = next(scenario for scenario in forecast.scenarios if scenario.nom == "Central")
    observations = _load_observations(
        Path(dataset_path) if dataset_path is not None else DEFAULT_DATASET
    )
    latest = observations[-1]
    scenario_brent = central.brent_usd_bbl * (1 + brent_change_pct / 100)
    scenario_spread = central.crack_spread_usd_bbl * (1 + crack_spread_change_pct / 100)
    projected_price = max(0.0, (scenario_brent + scenario_spread) / 42)
    brent_contribution = (scenario_brent - float(latest["brent_usd_bbl"])) / 42
    spread_contribution = (scenario_spread - float(latest["crack_spread_usd_bbl"])) / 42
    change_pct = (projected_price / forecast.dernier_prix_ulsd_usd_gal - 1) * 100

    if abs(change_pct) < 0.05:
        direction = "resterait stable"
    elif change_pct > 0:
        direction = "augmenterait"
    else:
        direction = "baisserait"

    explanation = (
        f"Si le Brent varie de {brent_change_pct:+.1f} % et le crack spread de "
        f"{crack_spread_change_pct:+.1f} % par rapport au scenario central, le prix "
        f"{direction} de {abs(change_pct):.1f} % par rapport au dernier prix observe. "
        f"Effet du Brent : {brent_contribution:+.3f} USD/gallon; effet du crack spread : "
        f"{spread_contribution:+.3f} USD/gallon."
    )
    return GasoilScenario(
        nom="Simulation personnalisee",
        brent_usd_bbl=scenario_brent,
        crack_spread_usd_bbl=scenario_spread,
        prix_ulsd_usd_gal=projected_price,
        variation_vs_dernier_pct=change_pct,
        contribution_brent_usd_gal=brent_contribution,
        contribution_spread_usd_gal=spread_contribution,
        explication=explanation,
    )
