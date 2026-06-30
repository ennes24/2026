"""Synthetic raw-data generator that stands in for the public sources listed
in the README (USDA NASS Quick Stats, NOAA NCEI, US Drought Monitor, USDA
Cropland Data Layer, USGS Water Use Data).

The real APIs require registration/API keys and large bulk downloads that
are not reproducible inside a sandboxed session, so this module produces a
statistically realistic stand-in panel with the same schema. Swap any of the
``data/raw/*.csv`` outputs with real downloads (same column names) and the
rest of the pipeline (data_loader -> model -> optimizer) runs unchanged.

Run as a script to (re)generate everything under ``data/raw/``:

    python -m src.generate_synthetic_data
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

START_YEAR = 2000
END_YEAR = 2023
CROPS = ["corn", "soybean", "wheat"]

# State climate normals (approximate, illustrative only): avg growing-season
# temperature (F), avg precipitation (in), baseline drought index (0=none,
# 4=exceptional, loosely modeled on the US Drought Monitor D0-D4 scale).
STATE_PROFILES = {
    "IA": {"temp": 70.0, "precip": 34.0, "drought": 0.6, "cropland_m_acres": 26.0},
    "IL": {"temp": 72.0, "precip": 38.0, "drought": 0.6, "cropland_m_acres": 24.0},
    "NE": {"temp": 71.0, "precip": 24.0, "drought": 1.1, "cropland_m_acres": 19.0},
    "MN": {"temp": 67.0, "precip": 30.0, "drought": 0.7, "cropland_m_acres": 21.0},
    "IN": {"temp": 71.0, "precip": 40.0, "drought": 0.5, "cropland_m_acres": 13.0},
    "KS": {"temp": 73.0, "precip": 26.0, "drought": 1.4, "cropland_m_acres": 27.0},
    "OH": {"temp": 70.0, "precip": 39.0, "drought": 0.5, "cropland_m_acres": 11.0},
    "SD": {"temp": 68.0, "precip": 21.0, "drought": 1.3, "cropland_m_acres": 17.0},
    "MO": {"temp": 73.0, "precip": 40.0, "drought": 0.8, "cropland_m_acres": 14.0},
    "ND": {"temp": 64.0, "precip": 18.0, "drought": 1.2, "cropland_m_acres": 27.0},
    "WI": {"temp": 66.0, "precip": 32.0, "drought": 0.6, "cropland_m_acres": 9.0},
    "TX": {"temp": 78.0, "precip": 22.0, "drought": 1.8, "cropland_m_acres": 24.0},
}

# Crop agronomy parameters used only to *simulate* a realistic yield surface.
CROP_PARAMS = {
    "corn": {
        "base_yield": 175.0,       # bu/acre at optimal climate
        "opt_temp": 71.0,
        "temp_sensitivity": 0.045,  # yield loss per (deg F)^2 away from optimum
        "opt_precip": 32.0,
        "precip_sensitivity": 0.012,
        "drought_sensitivity": 0.16,  # fractional yield loss per drought-index unit
        "tech_trend_per_year": 0.014,  # ~1.4%/yr genetics & ag-tech gain
        "noise_sd": 7.0,
        "water_use_acre_in": 22.0,
        "price_per_bu": 4.3,
    },
    "soybean": {
        "base_yield": 52.0,
        "opt_temp": 73.0,
        "temp_sensitivity": 0.040,
        "opt_precip": 30.0,
        "precip_sensitivity": 0.010,
        "drought_sensitivity": 0.13,
        "tech_trend_per_year": 0.011,
        "noise_sd": 3.0,
        "water_use_acre_in": 18.0,
        "price_per_bu": 11.5,
    },
    "wheat": {
        "base_yield": 48.0,
        "opt_temp": 64.0,
        "temp_sensitivity": 0.030,
        "opt_precip": 20.0,
        "precip_sensitivity": 0.014,
        "drought_sensitivity": 0.10,
        "tech_trend_per_year": 0.008,
        "noise_sd": 4.0,
        "water_use_acre_in": 15.0,
        "price_per_bu": 6.2,
    },
}


def _simulate_climate(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    years = np.arange(START_YEAR, END_YEAR + 1)
    for state, prof in STATE_PROFILES.items():
        # Mild warming trend + a handful of regional drought episodes shared
        # across nearby states in the same year (e.g. 2012, 2022 droughts).
        for year in years:
            year_idx = year - START_YEAR
            warming = 0.035 * year_idx  # ~0.84F over 24 years, consistent w/ obs trend
            drought_shock = 0.0
            if year in (2002, 2006, 2012, 2017, 2022):
                drought_shock = rng.uniform(0.8, 1.8)

            avg_temp = prof["temp"] + warming + rng.normal(0, 1.4)
            max_temp = avg_temp + rng.uniform(14, 20)
            min_temp = avg_temp - rng.uniform(14, 20)
            precip = max(
                4.0,
                prof["precip"] * (1 - 0.06 * drought_shock) + rng.normal(0, 3.5),
            )
            drought_index = float(
                np.clip(prof["drought"] + drought_shock + rng.normal(0, 0.4), 0, 4)
            )
            rows.append(
                {
                    "state": state,
                    "year": int(year),
                    "avg_temp_f": round(avg_temp, 2),
                    "max_temp_f": round(max_temp, 2),
                    "min_temp_f": round(min_temp, 2),
                    "precip_in": round(precip, 2),
                    "drought_index": round(drought_index, 3),
                }
            )
    return pd.DataFrame(rows)


def _simulate_cropland(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for state, prof in STATE_PROFILES.items():
        base_acres = prof["cropland_m_acres"] * 1_000_000
        for year in range(START_YEAR, END_YEAR + 1):
            drift = 1 + 0.0008 * (year - START_YEAR)  # slow cropland growth
            noise = rng.normal(1.0, 0.01)
            rows.append(
                {
                    "state": state,
                    "year": year,
                    "total_cropland_acres": int(base_acres * drift * noise),
                }
            )
    return pd.DataFrame(rows)


def _simulate_water_use(rng: np.random.Generator) -> pd.DataFrame:
    """Irrigation water budget available per state (acre-inches per acre of
    cropland), proxying USGS agricultural water-use survey data. Drier,
    high-irrigation states (NE, KS, TX) carry larger budgets."""
    irrigation_intensity = {
        "IA": 2.0, "IL": 2.0, "NE": 14.0, "MN": 3.0, "IN": 2.0, "KS": 11.0,
        "OH": 1.5, "SD": 4.0, "MO": 3.5, "ND": 2.5, "WI": 3.0, "TX": 13.0,
    }
    rows = []
    for state, base in irrigation_intensity.items():
        for year in range(START_YEAR, END_YEAR + 1):
            noise = rng.normal(1.0, 0.05)
            rows.append(
                {
                    "state": state,
                    "year": year,
                    "irrigation_acre_in_per_acre": round(max(0.5, base * noise), 2),
                }
            )
    return pd.DataFrame(rows)


def _simulate_yield(climate: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for _, c in climate.iterrows():
        for crop in CROPS:
            p = CROP_PARAMS[crop]
            year_idx = c["year"] - START_YEAR
            temp_penalty = p["temp_sensitivity"] * (c["avg_temp_f"] - p["opt_temp"]) ** 2
            precip_gap = c["precip_in"] - p["opt_precip"]
            precip_penalty = p["precip_sensitivity"] * (precip_gap**2) / max(p["opt_precip"], 1)
            drought_penalty = p["drought_sensitivity"] * c["drought_index"]
            tech_gain = p["tech_trend_per_year"] * year_idx

            multiplier = (1 - temp_penalty / 10) * (1 - precip_penalty) * (1 - drought_penalty)
            multiplier = max(0.15, multiplier) * (1 + tech_gain)

            yield_val = p["base_yield"] * multiplier + rng.normal(0, p["noise_sd"])
            yield_val = max(5.0, yield_val)
            rows.append(
                {
                    "state": c["state"],
                    "year": int(c["year"]),
                    "crop": crop,
                    "yield_bu_acre": round(yield_val, 2),
                }
            )
    return pd.DataFrame(rows)


def generate_all(seed: int = 42, out_dir: Path = RAW_DIR) -> None:
    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    climate = _simulate_climate(rng)
    cropland = _simulate_cropland(rng)
    water = _simulate_water_use(rng)
    yields = _simulate_yield(climate, rng)

    climate.to_csv(out_dir / "noaa_climate.csv", index=False)
    cropland.to_csv(out_dir / "cropland_data_layer.csv", index=False)
    water.to_csv(out_dir / "usgs_water_use.csv", index=False)
    yields.to_csv(out_dir / "usda_nass_yield.csv", index=False)

    # Drought Monitor is folded into the climate file's drought_index column
    # but also emitted standalone to mirror the README's data source table.
    climate[["state", "year", "drought_index"]].to_csv(
        out_dir / "drought_monitor.csv", index=False
    )

    print(f"Wrote synthetic raw data for {len(STATE_PROFILES)} states, "
          f"{START_YEAR}-{END_YEAR}, crops={CROPS} -> {out_dir}")


if __name__ == "__main__":
    generate_all()
