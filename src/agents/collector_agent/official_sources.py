"""Collect official commodity, trade, and exchange-rate source data."""
from __future__ import annotations

import io
import json
import os
import time
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "raw"
HEADERS = {
    "User-Agent": "HackFinance-data-collector/1.0",
    "Accept": "text/html,application/json,application/xml;q=0.9,*/*;q=0.8",
}
if contact := os.getenv("COLLECTOR_CONTACT"):
    HEADERS["User-Agent"] += f" (contact: {contact})"

WB_PINKSHEET = (
    "https://thedocs.worldbank.org/en/doc/"
    "5d903e848db1d1b83e0ec8f744e55570-0350012021/related/"
    "CMO-Historical-Data-Monthly.xlsx"
)
IMF_PCPS = {
    "POILAPSP": "brent_proxy_crude",
    "PWHEAMT": "wheat",
    "PMAIZMT": "maize",
    "PALUM": "aluminum",
    "PCOPP": "copper",
    "PIORECR": "iron_ore",
    "PGOLD": "gold_usd_oz",
}
BCT_FX_MONTHLY = (
    "https://www.bct.gov.tn/bct/siteprod/tableau_statistique.jsp"
    "?la=FR&params=PL213010"
)
INS_TRADE_PAGE = "https://www.ins.tn/statistiques/50"
WB_API = "https://api.worldbank.org/v2"
FRED_ALUMINIUM = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PALUMUSDM"


class Collector:
    def __init__(self, timeout: int = 60) -> None:
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.timeout = timeout

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20))
    def get(self, url: str, **kwargs: Any) -> requests.Response:
        time.sleep(0.4)
        response = self.session.get(url, timeout=self.timeout, **kwargs)
        response.raise_for_status()
        return response

    def save(self, frame: pd.DataFrame, name: str) -> Path:
        OUT.mkdir(parents=True, exist_ok=True)
        result = frame.copy()
        result["collected_at"] = date.today().isoformat()
        path = OUT / f"{name}.csv"
        result.to_csv(path, index=False, encoding="utf-8")
        return path

    def save_raw(self, content: bytes, name: str, suffix: str) -> Path:
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / f"{name}_{date.today().isoformat()}{suffix}"
        path.write_bytes(content)
        return path


def collect_wb_pinksheet(collector: Collector) -> pd.DataFrame:
    raw = collector.get(WB_PINKSHEET).content
    collector.save_raw(raw, "wb_pinksheet", ".xlsx")
    workbook = pd.ExcelFile(io.BytesIO(raw))
    sheet = "Monthly Prices" if "Monthly Prices" in workbook.sheet_names else workbook.sheet_names[0]
    preview = pd.read_excel(workbook, sheet_name=sheet, header=None, nrows=20)
    header_rows = preview.index[
        preview.astype(str).apply(
            lambda row: row.str.contains("alumin", case=False, na=False).any(), axis=1
        )
    ]
    if len(header_rows) == 0:
        raise RuntimeError("En-tete des series introuvable dans le Pink Sheet")
    frame = pd.read_excel(workbook, sheet_name=sheet, header=int(header_rows[0]))
    frame = frame.rename(columns={frame.columns[0]: "period"})
    unit_row = frame.iloc[0] if not frame.empty else pd.Series(dtype=object)
    units = {
        str(column): str(unit_row[column])
        for column in frame.columns[1:]
        if pd.notna(unit_row.get(column))
    }
    period_mask = frame["period"].astype(str).str.fullmatch(r"\d{4}M\d{2}", na=False)
    frame = frame.loc[period_mask].copy()
    result = frame.melt(id_vars=["period"], var_name="series_raw", value_name="value")
    result["value"] = pd.to_numeric(result["value"], errors="coerce")
    result = result.dropna(subset=["value"])
    result["source"] = "world_bank_pinksheet"
    result["unit"] = result["series_raw"].map(units).fillna("see_wb_legend")
    result["frequency"] = "M"
    return result


def collect_imf_pcps(
    collector: Collector,
    start: str = "2010-01",
    commodity_codes: list[str] | None = None,
) -> pd.DataFrame:
    codes = commodity_codes or list(IMF_PCPS)
    unknown_codes = set(codes) - IMF_PCPS.keys()
    if unknown_codes:
        raise ValueError(f"Codes PCPS inconnus: {sorted(unknown_codes)}")
    key = "+".join(codes)
    url = (
        "https://api.imf.org/external/sdmx/3.0/data/dataflow/"
        f"IMF.RES/PCPS/1.0/M.W00.{key}.USD"
        f"?startPeriod={start}&format=csvdata"
    )
    response = collector.get(url)
    raw_name = "imf_pcps_aluminium" if codes == ["PALUM"] else "imf_pcps"
    collector.save_raw(response.content, raw_name, ".csv")
    frame = pd.read_csv(io.StringIO(response.text))
    columns = {column.lower(): column for column in frame.columns}
    time_col = next(
        (columns[key] for key in columns if "time" in key or "period" in key),
        frame.columns[0],
    )
    value_col = next(
        (columns[key] for key in columns if key in ("value", "obs_value")),
        frame.columns[-1],
    )
    commodity_col = next(
        (columns[key] for key in columns if "commodity" in key or "pcps" in key),
        None,
    )
    result = pd.DataFrame(
        {
            "period": frame[time_col],
            "commodity_code": (
                frame[commodity_col]
                if commodity_col
                else codes[0] if len(codes) == 1 else None
            ),
            "value": pd.to_numeric(frame[value_col], errors="coerce"),
        }
    )
    result["series"] = result["commodity_code"].map(IMF_PCPS)
    if commodity_codes is not None:
        result = result[result["commodity_code"].astype(str).isin(codes)]
    result["source"] = "imf_pcps"
    result["unit"] = "USD"
    result["frequency"] = "M"
    return result.dropna(subset=["value"])


def filter_wb_aluminium(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep only aluminum series from the World Bank Pink Sheet melt."""
    if "series_raw" not in frame.columns or "value" not in frame.columns:
        raise ValueError("Colonnes series_raw et value requises pour filtrer l'aluminium")
    mask = frame["series_raw"].astype(str).str.contains("alumin", case=False, na=False)
    result = frame.loc[mask].copy()
    result["value"] = pd.to_numeric(result["value"], errors="coerce")
    result = result.dropna(subset=["value"])
    result["series"] = "aluminum"
    return result


def filter_wb_benchmark(
    frame: pd.DataFrame, series_pattern: str, normalized_series: str
) -> pd.DataFrame:
    if "series_raw" not in frame.columns or "value" not in frame.columns:
        raise ValueError("Colonnes series_raw et value requises pour filtrer le Pink Sheet")
    mask = frame["series_raw"].astype(str).str.contains(
        series_pattern, case=False, na=False, regex=False
    )
    result = frame.loc[mask].copy()
    result["value"] = pd.to_numeric(result["value"], errors="coerce")
    result = result.dropna(subset=["value"])
    result["series"] = normalized_series
    return result


def collect_fred_market_series(
    collector: Collector, series_id: str, unit: str, frequency: str
) -> pd.DataFrame:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    response = collector.get(url)
    collector.save_raw(response.content, f"fred_{series_id.lower()}", ".csv")
    frame = pd.read_csv(io.StringIO(response.text))
    if not {"observation_date", series_id}.issubset(frame.columns):
        raise RuntimeError(f"Format inattendu pour la serie FRED {series_id}")
    frame["period"] = pd.to_datetime(frame["observation_date"], errors="coerce")
    frame["value"] = pd.to_numeric(frame[series_id], errors="coerce")
    result = frame.dropna(subset=["period", "value"])[["period", "value"]].copy()
    result["period"] = result["period"].dt.strftime("%Y-%m-%d")
    result["series"] = series_id
    result["source"] = f"FRED {series_id}"
    result["unit"] = unit
    result["frequency"] = frequency
    return result


def collect_fred_aluminium(collector: Collector) -> pd.DataFrame:
    """Fetch the monthly global aluminum benchmark (USD per metric ton)."""
    frame = collect_fred_market_series(collector, "PALUMUSDM", "USD/mt", "M")
    periods = pd.to_datetime(frame["period"], errors="coerce")
    result = pd.DataFrame(
        {
            "period": periods.dt.strftime("%Y-%m"),
            "value": frame["value"],
            "series": "aluminum",
            "source": "fred_PALUMUSDM",
            "unit": "USD/mt",
            "frequency": "M",
        }
    )
    return result.dropna(subset=["period", "value"])


def latest_fred_observation(
    collector: Collector, series_id: str
) -> tuple[date, float]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    response = collector.get(url)
    collector.save_raw(response.content, f"fred_{series_id.lower()}", ".csv")
    frame = pd.read_csv(io.StringIO(response.text))
    if not {"observation_date", series_id}.issubset(frame.columns):
        raise RuntimeError(f"Format inattendu pour la serie FRED {series_id}")
    frame[series_id] = pd.to_numeric(frame[series_id], errors="coerce")
    frame["observation_date"] = pd.to_datetime(
        frame["observation_date"], errors="coerce"
    )
    frame = frame.dropna(subset=["observation_date", series_id])
    if frame.empty:
        raise RuntimeError(f"Aucune observation disponible pour FRED {series_id}")
    row = frame.iloc[-1]
    return row["observation_date"].date(), float(row[series_id])


def latest_wb_observation(
    collector: Collector, indicator: str, years_back: int = 10
) -> tuple[date, float]:
    current_year = date.today().year
    payload = collector.get(
        f"{WB_API}/country/TUN/indicator/{indicator}",
        params={
            "format": "json",
            "per_page": 100,
            "date": f"{current_year - years_back}:{current_year}",
        },
    ).json()
    rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
    valid = [row for row in rows if row.get("value") is not None]
    if not valid:
        raise RuntimeError(f"Aucune observation World Bank pour {indicator}")
    row = max(valid, key=lambda item: int(item["date"]))
    return date(int(row["date"]), 1, 1), float(row["value"])


def latest_aluminium_price_tnd_t(
    collector: Collector | None = None,
) -> tuple[date, float, str]:
    active_collector = collector or Collector()
    price_date, price_usd_t = latest_fred_observation(active_collector, "PALUMUSDM")
    fx_date, usd_tnd = latest_wb_observation(active_collector, "PA.NUS.FCRF")
    if usd_tnd <= 0:
        raise RuntimeError("Le taux USD/TND World Bank doit etre positif")
    return price_date, price_usd_t * usd_tnd, f"FRED PALUMUSDM x World Bank PA.NUS.FCRF ({fx_date.year})"


def collect_aluminium_sources(
    collector: Collector, start: str = "2010-01"
) -> dict[str, Any]:
    """Collect global aluminum benchmarks; INS HS76 detail remains an export input."""
    artifacts: dict[str, Any] = {
        "imf_aluminium_note": (
            "Endpoint PCPS configure retourne HTTP 404; source IMF non utilisee."
        )
    }
    try:
        fred = collect_fred_aluminium(collector)
        if fred.empty:
            raise RuntimeError("FRED n'a retourne aucune observation PALUMUSDM")
        artifacts["fred_aluminium"] = str(
            collector.save(fred, "fred_aluminium_monthly")
        )
        artifacts["fred_latest_period"] = str(fred["period"].max())
    except Exception as error:
        artifacts["fred_aluminium_error"] = str(error)

    try:
        pinksheet = filter_wb_aluminium(collect_wb_pinksheet(collector))
        if pinksheet.empty:
            raise RuntimeError("Aucune serie aluminium trouvee dans le Pink Sheet")
        artifacts["wb_aluminium"] = str(
            collector.save(pinksheet, "wb_aluminium_pinksheet")
        )
    except Exception as error:
        artifacts["wb_aluminium_error"] = str(error)

    artifacts["ins_comex_note"] = (
        "Pour les importations tunisiennes HS76, exporter le cube Commerce exterieur "
        "depuis le portail INS; la page publique ne donne que des agregats."
    )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "aluminium_collection_manifest.json").write_text(
        json.dumps(artifacts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return artifacts


def _collect_wb_indicator(collector: Collector, indicator: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page = 1
    while True:
        payload = collector.get(
            f"{WB_API}/country/TUN/indicator/{indicator}",
            params={"format": "json", "per_page": 1000, "page": page},
        ).json()
        if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
            break
        rows.extend(row for row in payload[1] if row.get("value") is not None)
        if page >= int(payload[0].get("pages", page)):
            break
        page += 1
    return rows


def collect_wb_usd_tnd(collector: Collector) -> pd.DataFrame:
    rows = _collect_wb_indicator(collector, "PA.NUS.FCRF")
    return pd.DataFrame(
        [
            {
                "period": row["date"],
                "value": row["value"],
                "series": "USD_TND_period_average",
                "source": "worldbank_PA.NUS.FCRF",
                "unit": "TND_per_USD",
                "frequency": "A",
            }
            for row in rows
        ]
    )


def collect_wb_trade_tn(collector: Collector) -> pd.DataFrame:
    indicators = {
        "NE.IMP.GNFS.CD": "imports_current_usd",
        "NE.EXP.GNFS.CD": "exports_current_usd",
        "TM.VAL.MRCH.CD.WT": "merch_imports_usd",
        "TX.VAL.MRCH.CD.WT": "merch_exports_usd",
    }
    frames = []
    for code, name in indicators.items():
        frames.append(
            pd.DataFrame(
                [
                    {
                        "period": row["date"],
                        "value": row["value"],
                        "series": name,
                        "indicator": code,
                        "source": "worldbank_api",
                        "unit": "USD",
                        "frequency": "A",
                    }
                    for row in _collect_wb_indicator(collector, code)
                ]
            )
        )
    return pd.concat(frames, ignore_index=True)


def collect_bct_fx_monthly(collector: Collector) -> pd.DataFrame:
    response = collector.get(BCT_FX_MONTHLY)
    collector.save_raw(response.content, "bct_fx_monthly", ".html")
    tables = pd.read_html(io.StringIO(response.text))
    if not tables:
        raise RuntimeError("Aucune table HTML BCT; structure du site modifiee")
    raw = tables[0]
    raw.columns = [str(column).strip() for column in raw.columns]
    id_col = raw.columns[0]
    result = raw.melt(id_vars=[id_col], var_name="period", value_name="value")
    result = result.rename(columns={id_col: "indicator"})
    result["value"] = (
        result["value"]
        .astype(str)
        .str.replace("\xa0", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    result["value"] = pd.to_numeric(result["value"], errors="coerce")
    result["source"] = "bct_PL213010"
    result["frequency"] = "M"
    return result.dropna(subset=["value"])


def collect_bct_tmm_links(collector: Collector) -> dict[str, Any]:
    index = "https://www.bct.gov.tn/bct/siteprod/statistiques.jsp"
    try:
        html = collector.get(index).text
    except requests.RequestException:
        html = ""
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "bct_statistiques_index.html"
    path.write_text(html, encoding="utf-8")
    soup = BeautifulSoup(html, "lxml") if html else None
    links = []
    if soup:
        links = [
            {"text": anchor.get_text(" ", strip=True), "href": anchor.get("href")}
            for anchor in soup.select("a[href*='tableau_statistique']")
        ]
    (OUT / "bct_table_links.json").write_text(
        json.dumps(links, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"n_links": len(links), "index_saved": str(path)}


def collect_ins_trade_page(collector: Collector) -> pd.DataFrame:
    html = collector.get(INS_TRADE_PAGE).text
    collector.save_raw(html.encode("utf-8"), "ins_statistiques_50", ".html")
    try:
        tables = pd.read_html(io.StringIO(html))
    except ValueError:
        tables = []
    frames = []
    for index, table in enumerate(tables):
        table = table.copy()
        table["table_id"] = index
        table["source"] = "ins_tn_statistiques_50"
        frames.append(table)
    if not frames:
        return pd.DataFrame(
            [{"warning": "pas de table HTML", "url": INS_TRADE_PAGE, "source": "ins"}]
        )
    return pd.concat(frames, ignore_index=True)


def load_ins_dataportal_xlsx(path: str | Path) -> pd.DataFrame:
    frame = pd.read_excel(path)
    frame["source"] = "ins_dataportal_xlsx"
    return frame


def main(aluminium_only: bool = False) -> None:
    collector = Collector()
    artifacts: dict[str, Any] = {
        "imf_pcps_note": "Endpoint PCPS configure retourne HTTP 404; collecte ignoree."
    }
    if aluminium_only:
        artifacts = collect_aluminium_sources(collector)
        print(json.dumps(artifacts, ensure_ascii=False, indent=2))
        return
    jobs = {
        "wb_pinksheet": (collect_wb_pinksheet, "wb_pinksheet_long"),
        "wb_usd_tnd": (collect_wb_usd_tnd, "wb_usd_tnd"),
        "wb_trade_tn": (collect_wb_trade_tn, "wb_trade_tn"),
        "bct_fx": (collect_bct_fx_monthly, "bct_fx_monthly"),
        "ins_html": (collect_ins_trade_page, "ins_comex_html_tables"),
    }
    for key, (job, filename) in jobs.items():
        try:
            artifacts[key] = str(collector.save(job(collector), filename))
        except Exception as error:
            artifacts[f"{key}_error"] = str(error)
    try:
        artifacts["bct_index"] = collect_bct_tmm_links(collector)
    except Exception as error:
        artifacts["bct_index_error"] = str(error)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = OUT / "run_manifest.json"
    manifest.write_text(json.dumps(artifacts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(artifacts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Collecte de sources officielles")
    parser.add_argument(
        "--aluminium",
        action="store_true",
        help="Collecter uniquement les cours internationaux de l'aluminium",
    )
    main(aluminium_only=parser.parse_args().aluminium)