"""Load raw data sources, merge into a model-ready panel, and derive the
state-level land/water constraints used by the optimization stage.

``load_raw_sources`` will transparently regenerate the synthetic stand-in
data (see ``generate_synthetic_data.py``) if ``data/raw`` is empty, so real
USDA/NOAA/USGS extracts can simply be dropped in with matching filenames and
column names without touching this module.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.generate_synthetic_data import CROP_PARAMS, generate_all

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

RAW_FILES = {
    "yield": "usda_nass_yield.csv",
    "climate": "noaa_climate.csv",
    "drought": "drought_monitor.csv",
    "cropland": "cropland_data_layer.csv",
    "water": "usgs_water_use.csv",
}


def load_raw_sources(raw_dir: Path = RAW_DIR) -> dict[str, pd.DataFrame]:
    if not raw_dir.exists() or not any(raw_dir.glob("*.csv")):
        generate_all(out_dir=raw_dir)
    return {key: pd.read_csv(raw_dir / fname) for key, fname in RAW_FILES.items()}


def build_panel(raw: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Return a long-format panel: one row per (state, year, crop) with
    climate features and the yield target, ready for ML training."""
    raw = raw or load_raw_sources()

    climate = raw["climate"].drop(columns=["drought_index"], errors="ignore").merge(
        raw["drought"], on=["state", "year"], how="left"
    )
    panel = raw["yield"].merge(climate, on=["state", "year"], how="left")
    panel = panel.merge(raw["cropland"], on=["state", "year"], how="left")
    panel = panel.merge(raw["water"], on=["state", "year"], how="left")

    panel["water_use_acre_in"] = panel["crop"].map(
        {c: p["water_use_acre_in"] for c, p in CROP_PARAMS.items()}
    )
    panel["price_per_bu"] = panel["crop"].map(
        {c: p["price_per_bu"] for c, p in CROP_PARAMS.items()}
    )
    panel = panel.sort_values(["crop", "state", "year"]).reset_index(drop=True)
    return panel


def feature_columns() -> list[str]:
    return [
        "avg_temp_f",
        "max_temp_f",
        "min_temp_f",
        "precip_in",
        "drought_index",
        "total_cropland_acres",
    ]


def build_state_constraints(
    raw: dict[str, pd.DataFrame] | None = None,
    *,
    recent_years: int = 5,
    land_share_for_three_crops: float = 0.55,
) -> pd.DataFrame:
    """Derive per-state land and water budgets (averaged over the most
    recent ``recent_years``) used as RHS values in the LP/MIP optimizer.

    Only a share of total cropland is assumed available to corn/soy/wheat
    (the rest goes to other uses), and the water budget is expressed in
    acre-inches, consistent with ``water_use_acre_in`` in the panel.
    """
    raw = raw or load_raw_sources()
    max_year = raw["cropland"]["year"].max()
    cutoff = max_year - recent_years + 1

    cropland = raw["cropland"][raw["cropland"]["year"] >= cutoff]
    land = (
        cropland.groupby("state")["total_cropland_acres"]
        .mean()
        .mul(land_share_for_three_crops)
        .rename("available_land_acres")
    )

    water = raw["water"][raw["water"]["year"] >= cutoff]
    water_budget_per_acre = water.groupby("state")["irrigation_acre_in_per_acre"].mean()
    # Total acre-inch budget = per-acre irrigation intensity * available land,
    # i.e. how much supplemental water the state could apply across its
    # allocated corn/soy/wheat acreage.
    water_total = (water_budget_per_acre * land).rename("water_budget_acre_in")

    constraints = pd.concat([land, water_total], axis=1).reset_index()
    constraints.columns = ["state", "available_land_acres", "water_budget_acre_in"]
    return constraints


def save_processed(panel: pd.DataFrame, constraints: pd.DataFrame, out_dir: Path = PROCESSED_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    panel.to_csv(out_dir / "panel.csv", index=False)
    constraints.to_csv(out_dir / "state_constraints.csv", index=False)


def load_or_build_processed(out_dir: Path = PROCESSED_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    panel_path, constraints_path = out_dir / "panel.csv", out_dir / "state_constraints.csv"
    if panel_path.exists() and constraints_path.exists():
        return pd.read_csv(panel_path), pd.read_csv(constraints_path)

    raw = load_raw_sources()
    panel = build_panel(raw)
    constraints = build_state_constraints(raw)
    save_processed(panel, constraints, out_dir)
    return panel, constraints


if __name__ == "__main__":
    panel_df, constraints_df = load_or_build_processed()
    print(panel_df.head())
    print(constraints_df.head())
    print(f"panel rows: {len(panel_df)}, states: {panel_df['state'].nunique()}")
