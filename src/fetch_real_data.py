"""Fetch REAL data from USDA NASS Quick Stats, NOAA NCEI (CDO), the US
Drought Monitor data service, and USGS Water Use, to replace the synthetic
stand-in data in ``data/raw/`` with actual government data.

IMPORTANT: this cannot be run from inside the sandboxed agent session that
built the rest of this repo -- outbound network access to these government
domains is blocked by that environment's egress policy. Run it yourself on
a machine with normal internet access:

    pip install -r requirements.txt
    python -m src.fetch_real_data

It reads USDA_NASS_API_KEY and NOAA_NCEI_TOKEN from a ``.env`` file in the
repo root (already created, gitignored -- never commit it). The Drought
Monitor and USGS Water Use fetchers need no key.

Output files match the exact schema of the synthetic files they replace, so
nothing else in the pipeline (data_loader.py onward) needs to change:

    data/raw/usda_nass_yield.csv       state, year, crop, yield_bu_acre
    data/raw/cropland_data_layer.csv   state, year, total_cropland_acres
    data/raw/noaa_climate.csv          state, year, avg_temp_f, max_temp_f, min_temp_f, precip_in
    data/raw/drought_monitor.csv       state, year, drought_index
    data/raw/usgs_water_use.csv        state, year, irrigation_acre_in_per_acre

Because none of this could be executed/tested from the sandbox, the exact
field names below reflect each service's publicly documented interface at
the time of writing but have NOT been verified end-to-end. If a request
fails or a field is missing, please paste the error back so it can be
fixed -- the surrounding structure (states/years/output schema) will not
need to change even if individual field names do.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

RAW_DIR = ROOT / "data" / "raw"
STATES = ["IA", "IL", "NE", "MN", "IN", "KS", "OH", "SD", "MO", "ND", "WI", "TX"]
START_YEAR, END_YEAR = 2000, 2023

# 2-digit state FIPS codes, needed for NOAA CDO (locationid=FIPS:XX) and USDM.
STATE_FIPS = {
    "IA": "19", "IL": "17", "NE": "31", "MN": "27", "IN": "18", "KS": "20",
    "OH": "39", "SD": "46", "MO": "29", "ND": "38", "WI": "55", "TX": "48",
}

NASS_COMMODITY = {"corn": "CORN", "soybean": "SOYBEANS", "wheat": "WHEAT"}


# ---------------------------------------------------------------------------
# 1) USDA NASS Quick Stats -- yield (needs USDA_NASS_API_KEY)
# ---------------------------------------------------------------------------
def fetch_nass_yield(api_key: str) -> pd.DataFrame:
    url = "https://quickstats.nass.usda.gov/api/api_GET/"
    rows = []
    for crop, commodity in NASS_COMMODITY.items():
        params = {
            "key": api_key,
            "commodity_desc": commodity,
            "statisticcat_desc": "YIELD",
            "agg_level_desc": "STATE",
            "source_desc": "SURVEY",
            "freq_desc": "ANNUAL",
            "year__GE": START_YEAR,
            "year__LE": END_YEAR,
            "format": "JSON",
        }
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        for rec in data:
            state = rec.get("state_alpha")
            if state not in STATES:
                continue
            try:
                value = float(str(rec["Value"]).replace(",", ""))
            except (ValueError, TypeError):
                continue
            rows.append(
                {"state": state, "year": int(rec["year"]), "crop": crop, "yield_bu_acre": value}
            )
        time.sleep(0.5)
    return pd.DataFrame(rows).drop_duplicates(subset=["state", "year", "crop"])


# ---------------------------------------------------------------------------
# 2) USDA NASS Quick Stats -- cropland acreage, Census years only (needs key)
#    Census of Agriculture runs every 5 years; intervening years are
#    linearly interpolated so data_loader.py gets one row per state-year.
# ---------------------------------------------------------------------------
def fetch_nass_cropland(api_key: str) -> pd.DataFrame:
    url = "https://quickstats.nass.usda.gov/api/api_GET/"
    params = {
        "key": api_key,
        "commodity_desc": "AG LAND",
        "short_desc": "AG LAND, CROPLAND - ACRES",
        "agg_level_desc": "STATE",
        "source_desc": "CENSUS",
        "format": "JSON",
    }
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    rows = []
    for rec in data:
        state = rec.get("state_alpha")
        if state not in STATES:
            continue
        try:
            value = float(str(rec["Value"]).replace(",", ""))
        except (ValueError, TypeError):
            continue
        rows.append({"state": state, "year": int(rec["year"]), "total_cropland_acres": value})
    census = pd.DataFrame(rows).drop_duplicates(subset=["state", "year"]).sort_values(["state", "year"])

    # Interpolate/extend to every year in [START_YEAR, END_YEAR] per state.
    out = []
    for state, grp in census.groupby("state"):
        s = grp.set_index("year")["total_cropland_acres"].reindex(range(START_YEAR, END_YEAR + 1))
        s = s.interpolate(limit_direction="both")
        out.append(pd.DataFrame({"state": state, "year": s.index, "total_cropland_acres": s.values}))
    return pd.concat(out, ignore_index=True)


# ---------------------------------------------------------------------------
# 3) NOAA NCEI Climate Data Online (CDO) -- annual climate (needs NOAA_NCEI_TOKEN)
#    GSOY = Global Summary of the Year, station-level; averaged up to state.
# ---------------------------------------------------------------------------
def fetch_noaa_climate(token: str) -> pd.DataFrame:
    url = "https://www.ncei.noaa.gov/cdo-web/api/v2/data"
    headers = {"token": token}
    datatypes = {"TAVG": "avg_temp_f", "TMAX": "max_temp_f", "TMIN": "min_temp_f", "PRCP": "precip_in"}
    rows = []
    for state, fips in STATE_FIPS.items():
        for year in range(START_YEAR, END_YEAR + 1):
            params = {
                "datasetid": "GSOY",
                "locationid": f"FIPS:{fips}",
                "datatypeid": list(datatypes.keys()),
                "startdate": f"{year}-01-01",
                "enddate": f"{year}-12-31",
                "units": "standard",  # Fahrenheit / inches
                "limit": 1000,
            }
            resp = requests.get(url, params=params, headers=headers, timeout=60)
            if resp.status_code == 429:
                time.sleep(2)
                resp = requests.get(url, params=params, headers=headers, timeout=60)
            resp.raise_for_status()
            results = resp.json().get("results", [])
            by_type: dict[str, list[float]] = {k: [] for k in datatypes}
            for rec in results:
                if rec["datatype"] in by_type:
                    by_type[rec["datatype"]].append(rec["value"])
            row = {"state": state, "year": year}
            for dt, col in datatypes.items():
                vals = by_type[dt]
                row[col] = sum(vals) / len(vals) if vals else None
            rows.append(row)
            time.sleep(0.25)  # stay under NOAA's 5 req/sec limit
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 4) US Drought Monitor -- weekly D0-D4 area % -> annual weighted index
#    No key required. Endpoint per usdmdataservices.unl.edu docs.
# ---------------------------------------------------------------------------
def fetch_drought_monitor() -> pd.DataFrame:
    url = "https://usdmdataservices.unl.edu/api/StateStatistics/GetDroughtSeverityStatisticsByAreaPercent"
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
    rows = []
    for state in STATES:
        for year in range(START_YEAR, END_YEAR + 1):
            params = {
                "aoi": state,
                "startdate": f"01/01/{year}",
                "enddate": f"12/31/{year}",
                "statisticsType": 1,
            }
            resp = requests.get(url, params=params, headers=headers, timeout=60)
            resp.raise_for_status()
            try:
                weeks = resp.json()
            except ValueError as exc:
                raise RuntimeError(
                    f"Drought Monitor API did not return JSON for state={state} year={year}.\n"
                    f"URL requested: {resp.url}\n"
                    f"HTTP status: {resp.status_code}\n"
                    f"Response body (first 500 chars): {resp.text[:500]!r}\n"
                    f"-> Paste this whole message back so the endpoint/params can be fixed."
                ) from exc
            if not weeks:
                continue
            # Weighted index on a 0-4 scale: D0..D4 area% -> category midpoints.
            weighted = []
            for w in weeks:
                d0, d1, d2, d3, d4 = (float(w.get(k, 0) or 0) for k in ("D0", "D1", "D2", "D3", "D4"))
                weighted.append((d0 * 1 + d1 * 2 + d2 * 3 + d3 * 4 + d4 * 5) / 100.0)
            rows.append({"state": state, "year": year, "drought_index": sum(weighted) / len(weighted)})
            time.sleep(0.2)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 5) USGS Water Use -- published every 5 years (2000/2005/2010/2015/2020);
#    intervening years are linearly interpolated, same approach as cropland.
#    No key required, but this is the least API-like of the five sources
#    (state data tables, not a REST endpoint) -- verify field names locally.
# ---------------------------------------------------------------------------
def fetch_usgs_water_use() -> pd.DataFrame:
    census_years = [2000, 2005, 2010, 2015, 2020]
    rows = []
    for year in census_years:
        url = f"https://water.usgs.gov/watuse/data/{year}/usco{year % 100:02d}.txt"
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        df = pd.read_csv(pd.io.common.StringIO(resp.text), sep="\t")
        df.columns = [c.strip() for c in df.columns]
        state_col = next(c for c in df.columns if c.upper() in ("STATE", "STATEFIPS", "STATE_ALPHA"))
        # Irrigation withdrawals per irrigated acre; column names vary by
        # year in USGS's layout (e.g. "IR-WTotl", "IR-Irtot") -- confirm
        # against that year's layout file and adjust below if this KeyErrors.
        withdrawal_col = next(c for c in df.columns if c.startswith("IR-W") and "Tot" in c)
        acres_col = next(c for c in df.columns if "IR" in c and "acre" in c.lower())
        for _, rec in df.iterrows():
            state = str(rec[state_col]).strip()
            if state not in STATES:
                continue
            withdrawal = pd.to_numeric(rec[withdrawal_col], errors="coerce")
            acres = pd.to_numeric(rec[acres_col], errors="coerce")
            if pd.isna(withdrawal) or pd.isna(acres) or acres == 0:
                continue
            # Mgal/day per irrigated acre -> rough acre-inch/acre/year proxy.
            intensity = (withdrawal * 1_000_000 / 325_851 * 365) / acres * 12
            rows.append({"state": state, "year": year, "irrigation_acre_in_per_acre": intensity})

    census = pd.DataFrame(rows).sort_values(["state", "year"])
    out = []
    for state, grp in census.groupby("state"):
        s = grp.set_index("year")["irrigation_acre_in_per_acre"].reindex(
            range(START_YEAR, END_YEAR + 1)
        )
        s = s.interpolate(limit_direction="both")
        out.append(pd.DataFrame({"state": state, "year": s.index, "irrigation_acre_in_per_acre": s.values}))
    return pd.concat(out, ignore_index=True)


def main():
    nass_key = os.environ["USDA_NASS_API_KEY"]
    noaa_token = os.environ["NOAA_NCEI_TOKEN"]

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    steps = [
        ("[1/5] USDA NASS yield", lambda: fetch_nass_yield(nass_key), "usda_nass_yield.csv"),
        ("[2/5] USDA NASS cropland acreage (Census years, interpolated)",
         lambda: fetch_nass_cropland(nass_key), "cropland_data_layer.csv"),
        ("[3/5] NOAA NCEI climate (slow: ~288 requests, rate-limited)",
         lambda: fetch_noaa_climate(noaa_token), "noaa_climate.csv"),
        ("[4/5] US Drought Monitor", fetch_drought_monitor, "drought_monitor.csv"),
        ("[5/5] USGS water use (Census years, interpolated)",
         fetch_usgs_water_use, "usgs_water_use.csv"),
    ]

    failed = []
    for label, fetch_fn, out_name in steps:
        print(f"{label}...")
        out_path = RAW_DIR / out_name
        try:
            fetch_fn().to_csv(out_path, index=False)
            print(f"  -> saved {out_path}")
        except Exception as exc:  # noqa: BLE001 -- surface any source's failure, keep going
            print(f"  !! FAILED: {exc}\n")
            failed.append(out_name)

    if failed:
        print(f"\nDone with errors. These files were NOT updated (synthetic data, if any, is still there): {failed}")
        print("Paste the error message(s) above back to fix the affected fetcher(s), then re-run this script.")
    else:
        print("\nAll 5 sources fetched successfully.")
    print("Next (once all 5 succeed): rmdir /s /q data\\processed  &&  rmdir /s /q outputs  &&  python -m src.run_pipeline")


if __name__ == "__main__":
    main()
