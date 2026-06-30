"""Plotting helpers for EDA, model evaluation, and the optimization /
scenario results. All functions save a PNG under ``outputs/figures`` and
also return the Matplotlib ``Figure`` for inline notebook display.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = ROOT / "outputs" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid")


def _save(fig, name: str):
    fig.tight_layout()
    fig.savefig(FIG_DIR / name, dpi=150)
    return fig


def plot_climate_yield_relationship(panel: pd.DataFrame, crop: str):
    sub = panel[panel["crop"] == crop]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    sns.scatterplot(data=sub, x="avg_temp_f", y="yield_bu_acre", hue="state", ax=axes[0], legend=False)
    axes[0].set_title(f"{crop}: avg temp vs yield")
    sns.scatterplot(data=sub, x="precip_in", y="yield_bu_acre", hue="state", ax=axes[1], legend=False)
    axes[1].set_title(f"{crop}: precipitation vs yield")
    sns.scatterplot(data=sub, x="drought_index", y="yield_bu_acre", hue="state", ax=axes[2], legend=False)
    axes[2].set_title(f"{crop}: drought index vs yield")
    return _save(fig, f"eda_{crop}_climate_relationships.png")


def plot_yield_trend(panel: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(9, 5))
    trend = panel.groupby(["year", "crop"])["yield_bu_acre"].mean().reset_index()
    sns.lineplot(data=trend, x="year", y="yield_bu_acre", hue="crop", marker="o", ax=ax)
    ax.set_title("US average yield by crop over time (synthetic panel)")
    return _save(fig, "eda_yield_trend.png")


def plot_model_comparison(comparison: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.barplot(data=comparison, x="crop", y="rmse", hue="model", ax=ax)
    ax.set_title("Test RMSE by model and crop (lower is better)")
    ax.set_ylabel("RMSE (bu/acre)")
    return _save(fig, "model_comparison_rmse.png")


def plot_feature_importance(fi: pd.Series, crop: str, model_name: str):
    fig, ax = plt.subplots(figsize=(7, 4))
    fi.sort_values().plot.barh(ax=ax)
    ax.set_title(f"Feature importance - {crop} ({model_name})")
    return _save(fig, f"feature_importance_{crop}.png")


def plot_actual_vs_predicted(y_true, y_pred, crop: str, model_name: str):
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(y_true, y_pred, alpha=0.6)
    lims = [min(min(y_true), min(y_pred)), max(max(y_true), max(y_pred))]
    ax.plot(lims, lims, "r--", lw=1)
    ax.set_xlabel("Actual yield (bu/acre)")
    ax.set_ylabel("Predicted yield (bu/acre)")
    ax.set_title(f"{crop} actual vs predicted ({model_name})")
    return _save(fig, f"actual_vs_predicted_{crop}.png")


def plot_allocation_heatmap(allocation: pd.DataFrame, title: str, fname: str):
    pivot = allocation.pivot(index="state", columns="crop", values="acres")
    fig, ax = plt.subplots(figsize=(7, 6))
    sns.heatmap(pivot, annot=True, fmt=",.0f", cmap="YlGn", ax=ax)
    ax.set_title(title)
    return _save(fig, fname)


def plot_scenario_comparison(summary: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(7, 5))
    sns.barplot(data=summary, x="scenario", y="total_production_bu", hue="scenario", ax=ax, palette="viridis", legend=False)
    ax.set_title("Total production: baseline vs drought (no adapt) vs drought (adapted)")
    ax.set_ylabel("Total production (bu)")
    for tick in ax.get_xticklabels():
        tick.set_rotation(15)
    return _save(fig, "scenario_comparison.png")


def plot_allocation_shift(baseline_alloc: pd.DataFrame, adapted_alloc: pd.DataFrame):
    base = baseline_alloc.groupby("crop")["acres"].sum().rename("baseline")
    adapt = adapted_alloc.groupby("crop")["acres"].sum().rename("drought_adapted")
    combo = pd.concat([base, adapt], axis=1).reset_index()
    melted = combo.melt(id_vars="crop", var_name="scenario", value_name="acres")
    fig, ax = plt.subplots(figsize=(7, 5))
    sns.barplot(data=melted, x="crop", y="acres", hue="scenario", ax=ax)
    ax.set_title("Total acres by crop: baseline vs drought-adapted allocation")
    return _save(fig, "allocation_shift_by_crop.png")
