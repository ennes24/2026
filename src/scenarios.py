"""Connects Stage 1 (yield prediction) to Stage 2 (allocation optimization)
across climate scenarios, and quantifies the value of reallocating acreage
in response to climate stress.

Two scenarios:
  * baseline   - recent 5-year average climate per state
  * drought_heat - baseline + warming, reduced precipitation, and elevated
    drought index, representing an intensified drought/heat year

For each scenario we predict yields with the Stage-1 models, then compute
three production numbers:
  1. baseline_production   - optimal allocation under baseline climate, baseline yields
  2. no_adapt_production   - baseline allocation, but drought-scenario yields applied
                              (climate worsens, farmers don't change what they planted)
  3. adapted_production    - re-optimized allocation under drought-scenario yields

"production saved by adaptation" = adapted_production - no_adapt_production.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.data_loader import feature_columns, load_or_build_processed
from src.model import load_best_models
from src.optimizer import optimize_allocation, production_from_fixed_allocation

CLIMATE_SHIFT = {
    # Applied on top of each state's recent-average climate to build the
    # "drought_heat" scenario. Roughly modeled on observed US Corn Belt /
    # Plains drought years (e.g. 2012).
    "avg_temp_f": +3.0,
    "max_temp_f": +4.0,
    "min_temp_f": +2.0,
    "precip_in_mult": 0.75,
    "drought_index_add": 1.6,
}


@dataclass
class ScenarioYields:
    name: str
    climate: pd.DataFrame  # per-state feature row used for prediction
    yields: pd.DataFrame  # state, crop, yield_bu_acre


def _recent_state_climate(panel: pd.DataFrame, recent_years: int = 5) -> pd.DataFrame:
    max_year = panel["year"].max()
    recent = panel[panel["year"] >= max_year - recent_years + 1]
    cols = feature_columns()
    return recent.groupby("state")[cols].mean().reset_index()


def build_scenarios(panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    baseline = _recent_state_climate(panel)

    drought = baseline.copy()
    drought["avg_temp_f"] += CLIMATE_SHIFT["avg_temp_f"]
    drought["max_temp_f"] += CLIMATE_SHIFT["max_temp_f"]
    drought["min_temp_f"] += CLIMATE_SHIFT["min_temp_f"]
    drought["precip_in"] *= CLIMATE_SHIFT["precip_in_mult"]
    drought["drought_index"] = (
        drought["drought_index"] + CLIMATE_SHIFT["drought_index_add"]
    ).clip(upper=4.0)

    return {"baseline": baseline, "drought_heat": drought}


def predict_scenario_yields(climate_by_state: pd.DataFrame, models: dict) -> pd.DataFrame:
    cols = feature_columns()
    rows = []
    for crop, model in models.items():
        preds = model.predict(climate_by_state[cols])
        for state, pred in zip(climate_by_state["state"], preds):
            rows.append({"state": state, "crop": crop, "yield_bu_acre": max(0.0, float(pred))})
    return pd.DataFrame(rows)


#: National crop-mix policy floor (e.g. crop rotation / food-security
#: requirements), expressed as a share of the *national water budget*
#: committed to each crop -- water, not land, is the binding resource here
#: (in the unconstrained LP, land headroom is never exhausted; the most
#: water-efficient crop is grown until the water budget runs out). Defined
#: independently of any optimizer output so it does not collapse to zero
#: when the unconstrained LP would pick a single crop everywhere, and the
#: shares are kept comfortably under 1.0 so a feasible solution always
#: exists (see optimizer.py design note).
CROP_MIN_WATER_SHARE = {"corn": 0.20, "soybean": 0.20, "wheat": 0.15}

#: Monoculture-prevention cap: without an upper bound, the most
#: water-efficient crop (corn) silently absorbs every acre of spare
#: capacity and the min-share floors above become the only thing forcing
#: diversification. Expressed the same way, as a share of the national
#: water budget.
CROP_MAX_WATER_SHARE = {"corn": 0.45}


def run_scenario_analysis(
    panel: pd.DataFrame | None = None,
    constraints: pd.DataFrame | None = None,
    models: dict | None = None,
    *,
    water_use: dict[str, float] | None = None,
    min_water_share: dict[str, float] | None = None,
):
    """Full Predict-then-Optimize pipeline across baseline vs drought_heat.

    Each crop's minimum required acreage is set by ``min_water_share`` (a
    national crop-rotation/food-security policy, e.g. "at least 20% of the
    national irrigation water budget must go to corn"), converted to acres
    via that crop's water use per acre. This is yield-independent by
    construction, so it cannot (a) collapse to zero the way a floor derived
    from the unconstrained optimizer's own degenerate single-crop output
    would (see README design note / optimizer.py), and (b) cannot become
    infeasible simply because a stress scenario lowers yields, which a
    *bushel* floor would. Because water (not land) is the actual binding
    resource here, and the shares sum to well under 1.0, the floors stay
    feasible while still keeping the drought scenario's reallocation
    problem non-trivial.
    """
    if panel is None or constraints is None:
        panel, constraints = load_or_build_processed()
    models = models or load_best_models()
    from src.generate_synthetic_data import CROP_PARAMS

    water_use = water_use or {c: p["water_use_acre_in"] for c, p in CROP_PARAMS.items()}
    min_water_share = min_water_share or CROP_MIN_WATER_SHARE

    scenario_climate = build_scenarios(panel)
    scenario_yields = {
        name: predict_scenario_yields(clim, models) for name, clim in scenario_climate.items()
    }

    total_water = constraints["water_budget_acre_in"].sum()
    min_acres = {
        c: (share * total_water) / water_use[c] for c, share in min_water_share.items()
    }
    max_acres = {
        c: (share * total_water) / water_use[c] for c, share in CROP_MAX_WATER_SHARE.items()
    }

    baseline_result = optimize_allocation(
        scenario_yields["baseline"],
        constraints,
        water_use=water_use,
        min_acres=min_acres,
        max_acres=max_acres,
    )

    no_adapt = production_from_fixed_allocation(
        baseline_result.allocation, scenario_yields["drought_heat"]
    )

    adapted_result = optimize_allocation(
        scenario_yields["drought_heat"],
        constraints,
        water_use=water_use,
        min_acres=min_acres,
        max_acres=max_acres,
    )

    summary = pd.DataFrame(
        [
            {"scenario": "baseline_optimal", "total_production_bu": baseline_result.allocation["production_bu"].sum()},
            {"scenario": "drought_no_adaptation", "total_production_bu": no_adapt["production_bu"].sum()},
            {"scenario": "drought_adapted", "total_production_bu": adapted_result.allocation["production_bu"].sum()},
        ]
    )
    saved = (
        summary.loc[summary.scenario == "drought_adapted", "total_production_bu"].values[0]
        - summary.loc[summary.scenario == "drought_no_adaptation", "total_production_bu"].values[0]
    )
    saved_pct = saved / summary.loc[summary.scenario == "drought_no_adaptation", "total_production_bu"].values[0] * 100

    return {
        "scenario_yields": scenario_yields,
        "baseline_result": baseline_result,
        "no_adapt_production": no_adapt,
        "adapted_result": adapted_result,
        "summary": summary,
        "production_saved_bu": saved,
        "production_saved_pct": saved_pct,
        "min_acres": min_acres,
    }


if __name__ == "__main__":
    from pathlib import Path

    out = run_scenario_analysis()
    print(out["summary"].to_string(index=False))
    print(f"\nProduction saved by reallocation under drought/heat: "
          f"{out['production_saved_bu']:,.0f} bu ({out['production_saved_pct']:.2f}%)")

    out_dir = Path(__file__).resolve().parent.parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out["summary"].to_csv(out_dir / "scenario_comparison.csv", index=False)
