"""Construction de cibles et de features mensuelles sans fuite temporelle."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PLASTIC_CODES = ("3901", "3902", "3903", "3904", "3907")
PROXY_WEIGHTS = {"Crude_average": 0.70, "Gas_Europe": 0.30}
ENERGY_ALIASES = {
    "Brent": ("brent",),
    "Crude_average": ("crudeaverage", "crudeavg", "crudeoilaverage"),
    "Gas_Europe": ("gaseurope", "europegas"),
    "Gas_US": ("gasus", "usgas", "henryhub"),
}
CONTEXT_ALIASES = {"Coal": ("coal",)}


def _normalise_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def _find_column(frame: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    names = {_normalise_name(column): str(column) for column in frame.columns}
    return next((names[alias] for alias in aliases if alias in names), None)


def read_table(path: str | Path) -> pd.DataFrame:
    """Lit un CSV ou un classeur Excel local, sans acces reseau."""
    source = Path(path)
    if source.suffix.casefold() == ".csv":
        return pd.read_csv(source, sep=None, engine="python")
    if source.suffix.casefold() == ".xlsx":
        return pd.read_excel(source)
    raise ValueError(f"Format non pris en charge: {source.suffix} (CSV ou XLSX attendu).")


def discover_sources(raw_dir: str | Path) -> dict[str, Path | None]:
    """Associe les fichiers locaux aux sources par leur nom de fichier."""
    files = sorted(
        path for path in Path(raw_dir).glob("*")
        if path.suffix.casefold() in {".csv", ".xlsx"}
    )

    def choose(pattern: str, excluded: tuple[str, ...] = ()) -> Path | None:
        return next(
            (path for path in files
             if re.search(pattern, _normalise_name(path.stem))
             and not any(token in _normalise_name(path.stem) for token in excluded)),
            None,
        )

    imports = choose(
        r"comex|import(?:ation)?s?|ins[_-]?comex|commerce[_-]?exterieur",
        excluded=("importance", "feature", "historique", "prediction"),
    )
    customs = choose(r"douane|tarif|custom")
    fx = choose(r"usdtnd|tauxchange|change")
    inflation = choose(r"inflation|ipc|cpi")
    excluded = {path for path in (imports, customs, fx, inflation) if path is not None}
    pink = choose(
        r"pinksheet|worldbank|plast|dataset|matiere",
        excluded=("comex", "import", "douane", "tarif", "custom",
                  "usdtnd", "inflation", "ipc", "cpi"),
    )
    if pink is None:
        pink = next((path for path in files if path not in excluded), None)
    return {"pink_sheet": pink, "imports": imports, "customs": customs, "usd_tnd": fx,
            "inflation": inflation}


def _date_column(frame: pd.DataFrame) -> str:
    column = _find_column(frame, ("date", "mois", "month", "periode", "period"))
    if column is None:
        raise ValueError("Colonne de date introuvable (Date/Mois/Month attendu).")
    return column


def _month_dates(values: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(values, errors="coerce")
    return parsed.dt.to_period("M").dt.to_timestamp()


def _numeric(values: pd.Series) -> pd.Series:
    if values.dtype == object:
        values = values.astype(str).str.replace(",", ".", regex=False)
    return pd.to_numeric(values, errors="coerce")


def prepare_energy(frame: pd.DataFrame) -> pd.DataFrame:
    """Nettoie et agrege les cours energie au premier jour de chaque mois."""
    date_col = _date_column(frame)
    dates = _month_dates(frame[date_col])
    result = pd.DataFrame(index=dates)
    for canonical, aliases in {**ENERGY_ALIASES, **CONTEXT_ALIASES}.items():
        source = _find_column(frame, aliases)
        if source is not None:
            result[canonical] = _numeric(frame[source]).to_numpy()
    result = result.loc[~result.index.isna()]
    result = result.groupby(level=0).mean(numeric_only=True).sort_index()
    result = result.loc[result.index >= pd.Timestamp("2000-01-01")]
    if result.empty:
        raise ValueError("Aucune observation energie valide depuis 2000.")
    return result


def _proxy_target(energy: pd.DataFrame) -> pd.Series:
    """Construit l'indice proxy, rebase sur la moyenne de l'annee 2010."""
    missing = set(PROXY_WEIGHTS).difference(energy.columns)
    if missing:
        raise ValueError(f"Colonnes requises pour le proxy absentes: {', '.join(sorted(missing))}.")
    components: dict[str, pd.Series] = {}
    for column in PROXY_WEIGHTS:
        base = energy.loc[energy.index.year == 2010, column].mean()
        if not np.isfinite(base) or base <= 0:
            raise ValueError(f"Impossible de calculer la base 2010 de {column}.")
        components[column] = energy[column] / base * 100.0
    proxy = sum(components[name] * weight for name, weight in PROXY_WEIGHTS.items())
    proxy.name = "target"
    return proxy


def _prepare_imports(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    date_col = _date_column(frame)
    code_col = _find_column(frame, ("codesh", "sh", "hs", "nomenclature", "code"))
    value_col = _find_column(frame, ("valeur", "value", "valeurimportee", "valuetnd"))
    quantity_col = _find_column(frame, ("quantite", "quantity", "poidsnet", "masse"))
    if code_col is None or value_col is None or quantity_col is None:
        raise ValueError("COMEX doit contenir date, code SH, valeur (TND) et quantite (kg).")
    data = pd.DataFrame({
        "date": _month_dates(frame[date_col]),
        "code_sh": frame[code_col].astype(str).str.extract(r"(\d{4})", expand=False),
        "value": _numeric(frame[value_col]),
        "quantity": _numeric(frame[quantity_col]),
    })
    data = data.loc[
        data["code_sh"].isin(PLASTIC_CODES) & data["date"].notna()
        & (data["quantity"] > 0) & (data["value"] > 0)
    ]
    if data.empty:
        raise ValueError("Aucune ligne COMEX exploitable pour les codes SH plastiques demandes.")
    monthly = data.groupby(["date", "code_sh"], as_index=False)[["value", "quantity"]].sum()
    monthly["target"] = monthly["value"] / monthly["quantity"]
    prices = monthly.pivot(index="date", columns="code_sh", values="target")
    quantities = monthly.pivot(index="date", columns="code_sh", values="quantity")
    prices.columns.name = None
    quantities.columns.name = None
    prices = prices.loc[prices.index >= pd.Timestamp("2000-01-01")]
    quantities = quantities.reindex(prices.index)
    return prices.sort_index(), quantities.sort_index()


def _optional_series(frame: pd.DataFrame | None, name: str,
                     aliases: tuple[str, ...]) -> pd.Series | None:
    if frame is None or frame.empty:
        return None
    date_col = _date_column(frame)
    value_col = _find_column(frame, aliases)
    if value_col is None:
        candidates = [column for column in frame.columns if column != date_col]
        value_col = next((column for column in candidates
                          if pd.api.types.is_numeric_dtype(frame[column])), None)
    if value_col is None:
        return None
    dates = _month_dates(frame[date_col])
    values = pd.Series(_numeric(frame[value_col]).to_numpy(), index=dates, name=name)
    values = values.loc[~values.index.isna()]
    return values.groupby(level=0).mean().sort_index()


def _customs_series(frame: pd.DataFrame | None, code: str,
                    index: pd.DatetimeIndex) -> pd.Series | None:
    if frame is None or frame.empty:
        return None
    date_col = _date_column(frame)
    code_col = _find_column(frame, ("codesh", "sh", "hs", "code"))
    rate_col = _find_column(frame, ("droitdedouane", "tauxdedouane", "tarif", "droit", "rate"))
    if rate_col is None:
        return None
    data = pd.DataFrame({"date": _month_dates(frame[date_col]), "rate": _numeric(frame[rate_col])})
    if code_col is not None:
        data["code_sh"] = frame[code_col].astype(str).str.extract(r"(\d{4})", expand=False)
        data = data.loc[data["code_sh"] == code]
    data = data.dropna(subset=["date", "rate"]).groupby("date")["rate"].last().sort_index()
    if data.empty:
        return None
    return data.reindex(index).ffill().rename("droit_douane")


def _series_features(target: pd.Series, energy: pd.DataFrame, index: pd.DatetimeIndex,
                     code: str, quantities: pd.DataFrame | None,
                     usd_tnd: pd.Series | None, inflation: pd.Series | None,
                     customs: pd.DataFrame | None) -> pd.DataFrame:
    frame = pd.DataFrame(index=index)
    target = target.reindex(index).astype(float)
    frame["target"] = target

    for column in ENERGY_ALIASES:
        if column not in energy:
            continue
        values = energy[column].reindex(index).astype(float)
        frame[column] = values
        for lag in (1, 2, 3, 6):
            frame[f"{column}_lag_{lag}"] = values.shift(lag)
        log_values = np.log(values.where(values > 0))
        for period in (1, 3, 12):
            frame[f"{column}_var_{period}"] = log_values.diff(period)
    if "Coal" in energy:
        frame["Coal"] = energy["Coal"].reindex(index).astype(float)

    log_target = np.log(target.where(target > 0))
    for lag in (1, 3, 12):
        frame[f"target_lag_{lag}"] = log_target.shift(lag) - log_target
    monthly_change = log_target.diff()
    frame["target_volatilite_6m"] = monthly_change.rolling(6, min_periods=6).std()
    rolling_mean = target.rolling(12, min_periods=12).mean()
    frame["target_ecart_moyenne_12m"] = target / rolling_mean - 1.0

    if usd_tnd is not None:
        frame["usd_tnd"] = usd_tnd.reindex(index).ffill()
    if inflation is not None:
        frame["inflation"] = inflation.reindex(index).ffill()
    if quantities is not None and code in quantities:
        quantity = quantities[code].reindex(index)
        frame["quantite_importee_cumulee_3m"] = quantity.rolling(3, min_periods=1).sum()
        frame["quantite_importee_cumulee_12m"] = quantity.rolling(12, min_periods=1).sum()
    tariff = _customs_series(customs, code, index)
    if tariff is not None:
        frame["droit_douane"] = tariff

    month = index.month
    frame["mois_sin"] = np.sin(2.0 * np.pi * month / 12.0)
    frame["mois_cos"] = np.cos(2.0 * np.pi * month / 12.0)
    if "Brent" in energy:
        brent = np.log(energy["Brent"].reindex(index).where(energy["Brent"].reindex(index) > 0))
    else:
        brent = pd.Series(np.nan, index=index)
    for horizon in (1, 3, 6, 12):
        frame[f"target_delta_{horizon}m"] = log_target.shift(-horizon) - log_target
        frame[f"baseline_brent_delta_{horizon}m"] = brent - brent.shift(horizon)
    frame.index.name = "date"
    return frame.replace([np.inf, -np.inf], np.nan)


def build_feature_table(energy_data: pd.DataFrame, imports_data: pd.DataFrame | None = None,
                        usd_tnd_data: pd.DataFrame | None = None,
                        inflation_data: pd.DataFrame | None = None,
                        customs_data: pd.DataFrame | None = None
                        ) -> tuple[pd.DataFrame, str, float]:
    """Retourne les features et la cible choisie automatiquement."""
    energy = prepare_energy(energy_data)
    imports = None
    quantities = None
    if imports_data is not None and not imports_data.empty:
        imports, quantities = _prepare_imports(imports_data)

    if imports is not None and not imports.empty:
        target_name = "prix_unitaire_importation"
        target_series = {code: imports[code].dropna() for code in imports.columns}
        proxy_share = 0.0
    else:
        target_name = "indice_cout_proxy_base_100_2010"
        proxy = _proxy_target(energy)
        target_series = {"proxy": proxy.dropna()}
        proxy_share = 1.0

    fx = _optional_series(usd_tnd_data, "usd_tnd", ("usdtnd", "usdtn", "valeur"))
    cpi = _optional_series(inflation_data, "inflation", ("inflation", "ipc", "cpi", "valeur"))
    end_date = max(series.index.max() for series in target_series.values() if not series.empty)
    full_index = pd.date_range("2000-01-01", end_date, freq="MS")
    tables = []
    for code, target in target_series.items():
        table = _series_features(target, energy, full_index, code, quantities, fx, cpi, customs_data)
        table["code_sh"] = code if code != "proxy" else ""
        tables.append(table.reset_index())
    result = pd.concat(tables, ignore_index=True)
    result["date"] = pd.to_datetime(result["date"]).dt.to_period("M").dt.to_timestamp()
    return result, target_name, proxy_share


def feature_columns(table: pd.DataFrame) -> list[str]:
    """Liste les colonnes explicatives, en excluant date, cible et metadonnees."""
    excluded = {"date", "code_sh", "target", "Coal"}
    return [
        column for column in table.columns
        if column not in excluded
        and not column.startswith("target_delta_")
        and not column.startswith("baseline_brent_delta_")
    ]