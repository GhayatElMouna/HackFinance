"""Calculs purs utilises par les outils de simulation et de verification T17."""

from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd

PROXY_WEIGHTS = {"Crude_average": 0.70, "Gas_Europe": 0.30}
UPLOAD_REQUIRED_COLUMNS = ("Date", "Brent", "Crude_average", "Gas_Europe", "Gas_US", "Coal")
PLASTIC_SH_CODES = ("3901", "3902", "3903", "3904", "3907")


def _normalise_column(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def proxy_index(crude_average: float, gas_europe: float,
                crude_base_2010: float, gas_base_2010: float) -> float:
    """Calcule l'indice proxy avec normalisation independante sur 2010."""
    if crude_base_2010 <= 0 or gas_base_2010 <= 0:
        raise ValueError("Les bases de normalisation 2010 doivent etre positives.")
    return (
        PROXY_WEIGHTS["Crude_average"] * crude_average / crude_base_2010 * 100.0
        + PROXY_WEIGHTS["Gas_Europe"] * gas_europe / gas_base_2010 * 100.0
    )


def convert_reference_band(reference_price: float, forecast_low: float,
                           forecast_central: float, forecast_high: float,
                           reference_index: float) -> dict[str, float]:
    """Convertit une bande d'indice en TND/kg par prorata du mois de reference."""
    if reference_index <= 0:
        raise ValueError("L'indice du mois de reference doit etre positif.")
    if not forecast_low <= forecast_central <= forecast_high:
        raise ValueError("La fourchette d'indice doit respecter bas <= central <= haut.")
    factor = reference_price / reference_index
    return {
        "bas": factor * forecast_low,
        "central": factor * forecast_central,
        "haut": factor * forecast_high,
    }


def validate_uploaded_csv(frame: pd.DataFrame) -> pd.DataFrame:
    """Valide et canonise un CSV Pink Sheet importe par l'utilisateur."""
    normalized = {_normalise_column(column): column for column in frame.columns}
    required = {_normalise_column(column): column for column in UPLOAD_REQUIRED_COLUMNS}
    missing = [label for key, label in required.items() if key not in normalized]
    if missing:
        raise ValueError("Colonnes requises absentes : " + ", ".join(missing))
    result = frame.rename(columns={normalized[key]: label for key, label in required.items()}).copy()
    result["Date"] = pd.to_datetime(result["Date"], errors="coerce")
    if result["Date"].isna().any():
        raise ValueError("La colonne Date contient des dates invalides.")
    for column in UPLOAD_REQUIRED_COLUMNS[1:]:
        result[column] = pd.to_numeric(result[column].astype(str).str.replace(",", ".", regex=False),
                                       errors="coerce")
    if result[["Crude_average", "Gas_Europe"]].isna().any().any():
        raise ValueError("Crude_average et Gas_Europe doivent contenir des valeurs numeriques.")
    for column in ("Crude_average", "Gas_Europe"):
        if (result[column] <= 0).any():
            raise ValueError(f"{column} doit rester strictement positif pour calculer l'indice.")
    if not (result["Date"].dt.year == 2010).any():
        raise ValueError("Le CSV doit contenir au moins une observation de l'annee 2010 pour normaliser l'indice.")
    return result.sort_values("Date").reset_index(drop=True)