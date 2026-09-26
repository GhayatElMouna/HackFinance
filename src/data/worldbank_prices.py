"""Chargement des series exogenes (World Bank Pink Sheet + FRED) dans data/raw."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
RAW_DIR = DATA_DIR / "raw"

# Cle UI -> serie (World Bank ou FRED)
FACTOR_CATALOG: dict[str, dict[str, str]] = {
    "brent": {
        "commodity": "Crude oil, Brent",
        "file": "brent_monthly.csv",
        "label_fr": "Pétrole Brent",
        "source": "worldbank",
    },
    "wti": {
        "commodity": "Crude oil, WTI",
        "file": "wti_monthly.csv",
        "label_fr": "Pétrole WTI",
        "source": "worldbank",
    },
    "charbon": {
        "commodity": "Coal, Australian",
        "file": "coal_monthly.csv",
        "label_fr": "Charbon australien",
        "source": "worldbank",
    },
    "gaz_europe": {
        "commodity": "Natural gas, Europe",
        "file": "gas_europe_monthly.csv",
        "label_fr": "Gaz Europe",
        "source": "worldbank",
    },
    "cuivre": {
        "commodity": "Copper",
        "file": "copper_monthly.csv",
        "label_fr": "Cuivre",
        "source": "worldbank",
    },
    "aluminium": {
        "commodity": "Aluminum",
        "file": "aluminum_monthly.csv",
        "label_fr": "Aluminium",
        "source": "worldbank",
    },
    "nickel": {
        "commodity": "Nickel",
        "file": "nickel_monthly.csv",
        "label_fr": "Nickel",
        "source": "worldbank",
    },
    "zinc": {
        "commodity": "Zinc",
        "file": "zinc_monthly.csv",
        "label_fr": "Zinc",
        "source": "worldbank",
    },
    "or": {
        "commodity": "Gold",
        "file": "gold_monthly.csv",
        "label_fr": "Or",
        "source": "worldbank",
    },
    # Macro / geopolitique (FRED)
    "usd": {
        "commodity": "USD Trade Weighted Index",
        "file": "usd_index_monthly.csv",
        "label_fr": "Indice dollar (USD)",
        "source": "fred",
        "fred_id": "DTWEXBGS",
        "unit": "index",
    },
    "risque_geo": {
        "commodity": "VIX Risk Aversion",
        "file": "vix_risk_monthly.csv",
        "label_fr": "Risque géopolitique (VIX)",
        "source": "fred",
        "fred_id": "VIXCLS",
        "unit": "index",
    },
}

# Cible fer/acier
TARGET = {
    "commodity": "Iron ore",
    "file": "iron_ore_monthly.csv",
    "source": "worldbank",
}

# Defauts : commodites + les 2 nouveaux facteurs macro/geo
DEFAULT_FACTORS = ["brent", "charbon", "cuivre", "usd", "risque_geo"]

__all__ = [
    "RAW_DIR",
    "FACTOR_CATALOG",
    "DEFAULT_FACTORS",
    "TARGET",
    "COMMODITY_FILES",
    "EXOG_FOR_STEEL",
    "EXOG_LABELS",
    "factor_options_fr",
    "resolve_factor_commodities",
    "load_commodity_series",
    "load_exog_frame",
]

COMMODITY_FILES = {
    TARGET["commodity"]: RAW_DIR / TARGET["file"],
    **{meta["commodity"]: RAW_DIR / meta["file"] for meta in FACTOR_CATALOG.values()},
}

EXOG_FOR_STEEL = [FACTOR_CATALOG[k]["commodity"] for k in DEFAULT_FACTORS]

EXOG_LABELS = {meta["commodity"]: key for key, meta in FACTOR_CATALOG.items()}


def factor_options_fr() -> dict[str, str]:
    """Map cle -> label francais pour Streamlit."""
    return {k: v["label_fr"] for k, v in FACTOR_CATALOG.items()}


def resolve_factor_commodities(factor_keys: list[str] | None) -> list[str]:
    keys = factor_keys if factor_keys is not None else DEFAULT_FACTORS
    out: list[str] = []
    for k in keys:
        if k in FACTOR_CATALOG:
            out.append(FACTOR_CATALOG[k]["commodity"])
    return out


def _meta_for_commodity(commodity: str) -> Optional[dict]:
    if commodity == TARGET["commodity"]:
        return TARGET
    for meta in FACTOR_CATALOG.values():
        if meta["commodity"] == commodity:
            return meta
    return None


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values("date").dropna(subset=["price"])
    return out[["date", "commodity", "price", "unit"]].reset_index(drop=True)


def _fetch_worldbank(commodity: str, start: str = "2010-01-01") -> Optional[pd.DataFrame]:
    try:
        from worldbank_commodities import WorldBankCommodities

        client = WorldBankCommodities()
        df = client.get_prices(freq="monthly", commodities=[commodity], start=start)
        if df is None or df.empty:
            return None
        return _normalize(df)
    except Exception:
        return None


def _fetch_fred(fred_id: str, commodity: str, unit: str = "index") -> Optional[pd.DataFrame]:
    """Telecharge une serie FRED (quotidienne) et agregue en mensuel."""
    try:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={fred_id}"
        raw = pd.read_csv(url)
        date_col = "observation_date" if "observation_date" in raw.columns else raw.columns[0]
        value_col = fred_id if fred_id in raw.columns else raw.columns[1]
        raw[date_col] = pd.to_datetime(raw[date_col])
        raw[value_col] = pd.to_numeric(raw[value_col], errors="coerce")
        monthly = (
            raw.dropna(subset=[value_col])
            .set_index(date_col)[value_col]
            .resample("MS")
            .mean()
            .dropna()
        )
        monthly = monthly[monthly.index >= "2010-01-01"]
        out = pd.DataFrame(
            {
                "date": monthly.index,
                "commodity": commodity,
                "price": monthly.values.astype(float),
                "unit": unit,
            }
        )
        return _normalize(out)
    except Exception:
        return None


def _fetch_live(commodity: str, start: str = "2010-01-01") -> Optional[pd.DataFrame]:
    meta = _meta_for_commodity(commodity)
    if meta is None:
        return _fetch_worldbank(commodity, start=start)
    if meta.get("source") == "fred":
        return _fetch_fred(
            meta["fred_id"],
            commodity=commodity,
            unit=meta.get("unit", "index"),
        )
    return _fetch_worldbank(commodity, start=start)


def load_commodity_series(
    commodity: str,
    *,
    refresh: bool = False,
    start: str = "2010-01-01",
) -> tuple[pd.DataFrame, str, bool]:
    """
    Retourne (dataframe, source, is_synthetic).
    Prefere le cache CSV dans data/raw ; refresh live si refresh=True.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = COMMODITY_FILES.get(commodity)
    meta = _meta_for_commodity(commodity)
    source_name = "FRED" if (meta or {}).get("source") == "fred" else "World Bank Pink Sheet"

    live = _fetch_live(commodity, start=start) if refresh else None
    if live is not None and not live.empty:
        if path is not None:
            live.to_csv(path, index=False)
        return live, f"{source_name} (live)", False

    if path is not None and path.exists():
        cached = _normalize(pd.read_csv(path))
        return cached, f"{source_name} (cache: {path.name})", False

    live = _fetch_live(commodity, start=start)
    if live is not None and not live.empty:
        if path is not None:
            live.to_csv(path, index=False)
        return live, f"{source_name} (live)", False

    dates = pd.date_range(start=start, periods=96, freq="MS")
    synth = pd.DataFrame(
        {
            "date": dates,
            "commodity": commodity,
            "price": 100 + (pd.Series(range(len(dates))) % 24) * 1.5,
            "unit": "USD",
        }
    )
    return synth, "synthetic", True


def load_exog_frame(
    commodities: list[str] | None = None,
    *,
    refresh: bool = False,
) -> pd.DataFrame:
    """DataFrame mensuel large : une colonne prix par commodite."""
    commodities = commodities if commodities is not None else EXOG_FOR_STEEL
    frames: list[pd.Series] = []
    for name in commodities:
        df, _, _ = load_commodity_series(name, refresh=refresh)
        s = df.set_index("date")["price"].rename(name)
        frames.append(s)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, axis=1).sort_index().asfreq("MS").interpolate().bfill().ffill()
