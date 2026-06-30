"""Stage 2 - constrained crop-allocation optimization (LP / MIP).

Decision variables: ``x[state, crop]`` = acres of each crop planted in each
state. The objective maximizes total production (bushels) or, optionally,
total revenue (bushels * price). Predicted yields from the Stage-1 ML models
feed in directly as the objective coefficients (Predict-then-Optimize).

As called out in the README design note, an unconstrained "maximize total
production" LP degenerates to planting only the single highest-yielding
crop everywhere. Two binding constraints make the trade-off real:

* land availability per state
* water budget per state (corn/soy/wheat differ in water use per acre)
* (optional) minimum required production per crop, e.g. food-security floor

A ``single_crop_per_state`` MIP variant is also provided, matching the
README's "이 지역엔 한 작물만" extension.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import pulp


@dataclass
class OptimizationResult:
    status: str
    objective_value: float
    allocation: pd.DataFrame  # columns: state, crop, acres
    summary_by_crop: pd.DataFrame = field(default_factory=pd.DataFrame)


def _pivot_yield(yield_df: pd.DataFrame) -> dict[tuple[str, str], float]:
    return {(r.state, r.crop): r.yield_bu_acre for r in yield_df.itertuples()}


def optimize_allocation(
    yield_df: pd.DataFrame,
    constraints_df: pd.DataFrame,
    *,
    water_use: dict[str, float],
    min_production: dict[str, float] | None = None,
    min_acres: dict[str, float] | None = None,
    max_acres: dict[str, float] | None = None,
    price: dict[str, float] | None = None,
    objective: str = "production",
    single_crop_per_state: bool = False,
) -> OptimizationResult:
    """Solve the land/water-constrained allocation LP (or MIP).

    Parameters
    ----------
    yield_df : columns [state, crop, yield_bu_acre] -- Stage-1 predictions
        for the climate scenario being optimized.
    constraints_df : columns [state, available_land_acres, water_budget_acre_in]
    water_use : crop -> acre-inches of water required per acre planted
    min_production : optional crop -> minimum total bushels required. Note
        this is expressed in yield-dependent units: if yields fall sharply
        in a stress scenario, hitting the same bushel floor can require
        more acreage than land/water allow, making the LP infeasible. Use
        ``min_acres`` instead for a yield-independent rotation/diversification
        floor that stays feasible across scenarios.
    min_acres : optional crop -> minimum total acres planted nationally
        (a crop-rotation / diversification policy floor, independent of
        predicted yield)
    max_acres : optional crop -> maximum total acres planted nationally
        (a monoculture-prevention / diversification cap, e.g. "no more than
        45% of the water budget's worth of acres to a single crop"). Without
        this, the highest bushel/water-inch crop (typically corn) silently
        absorbs all spare capacity and the other floors become the only
        thing forcing diversification.
    price : optional crop -> $/bushel, required if objective="revenue"
    objective : "production" (total bushels) or "revenue" (total $)
    single_crop_per_state : if True, adds binary "only one crop per state"
        constraints (MIP) instead of a continuous LP relaxation.
    """
    states = sorted(constraints_df["state"].unique())
    crops = sorted(yield_df["crop"].unique())
    yields = _pivot_yield(yield_df)
    land = constraints_df.set_index("state")["available_land_acres"].to_dict()
    water_budget = constraints_df.set_index("state")["water_budget_acre_in"].to_dict()

    prob = pulp.LpProblem("crop_allocation", pulp.LpMaximize)

    x = {
        (s, c): pulp.LpVariable(f"x_{s}_{c}", lowBound=0)
        for s in states
        for c in crops
    }

    coeff = {}
    for (s, c), y in yields.items():
        coeff[(s, c)] = y * price[c] if objective == "revenue" else y
    prob += pulp.lpSum(coeff.get((s, c), 0) * x[(s, c)] for s in states for c in crops)

    for s in states:
        prob += pulp.lpSum(x[(s, c)] for c in crops) <= land[s], f"land_{s}"
        prob += (
            pulp.lpSum(water_use[c] * x[(s, c)] for c in crops) <= water_budget[s],
            f"water_{s}",
        )

    if min_production:
        for c, min_bu in min_production.items():
            prob += (
                pulp.lpSum(yields.get((s, c), 0) * x[(s, c)] for s in states) >= min_bu,
                f"min_production_{c}",
            )

    if min_acres:
        for c, min_a in min_acres.items():
            prob += pulp.lpSum(x[(s, c)] for s in states) >= min_a, f"min_acres_{c}"

    if max_acres:
        for c, max_a in max_acres.items():
            prob += pulp.lpSum(x[(s, c)] for s in states) <= max_a, f"max_acres_{c}"

    if single_crop_per_state:
        big_m = {s: land[s] for s in states}
        z = {
            (s, c): pulp.LpVariable(f"z_{s}_{c}", cat="Binary")
            for s in states
            for c in crops
        }
        for s in states:
            prob += pulp.lpSum(z[(s, c)] for c in crops) <= 1, f"one_crop_{s}"
            for c in crops:
                prob += x[(s, c)] <= big_m[s] * z[(s, c)], f"link_{s}_{c}"

    solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)
    status = pulp.LpStatus[prob.status]

    rows = [
        {"state": s, "crop": c, "acres": x[(s, c)].value() or 0.0}
        for s in states
        for c in crops
    ]
    allocation = pd.DataFrame(rows)
    allocation["predicted_yield_bu_acre"] = allocation.apply(
        lambda r: yields.get((r.state, r.crop), 0.0), axis=1
    )
    allocation["production_bu"] = allocation["acres"] * allocation["predicted_yield_bu_acre"]

    summary_by_crop = (
        allocation.groupby("crop")[["acres", "production_bu"]].sum().reset_index()
    )

    return OptimizationResult(
        status=status,
        objective_value=pulp.value(prob.objective) or 0.0,
        allocation=allocation,
        summary_by_crop=summary_by_crop,
    )


def production_from_fixed_allocation(allocation: pd.DataFrame, yield_df: pd.DataFrame) -> pd.DataFrame:
    """Apply a *different* scenario's yields to an already-fixed allocation
    (e.g. baseline acreage exposed to drought yields) without re-solving --
    used to measure production lost when no adaptation happens."""
    yields = _pivot_yield(yield_df)
    out = allocation[["state", "crop", "acres"]].copy()
    out["predicted_yield_bu_acre"] = out.apply(
        lambda r: yields.get((r.state, r.crop), 0.0), axis=1
    )
    out["production_bu"] = out["acres"] * out["predicted_yield_bu_acre"]
    return out
