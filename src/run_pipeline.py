"""End-to-end pipeline runner: generate data -> train models -> run climate
scenario optimization -> save all figures. Useful for a single-command
reproduction of every artifact under ``outputs/``.

    python -m src.run_pipeline
"""
from __future__ import annotations

from src.data_loader import load_or_build_processed
from src.model import load_best_models, train_all_crops
from src.scenarios import run_scenario_analysis
from src import visualize as viz


def main():
    print("[1/4] Loading / building processed panel + constraints...")
    panel, constraints = load_or_build_processed()

    print("[2/4] Training yield prediction models (RF / XGBoost / LightGBM / CatBoost)...")
    results_by_crop, comparison = train_all_crops(panel)
    viz.plot_model_comparison(comparison)
    viz.plot_yield_trend(panel)
    for crop in panel["crop"].unique():
        viz.plot_climate_yield_relationship(panel, crop)
        best_name = results_by_crop[crop]["best"]
        tm = results_by_crop[crop]["results"][best_name]
        viz.plot_feature_importance(tm.feature_importance, crop, best_name)

    print("[3/4] Running climate scenario optimization (baseline vs drought/heat)...")
    models = load_best_models()
    out = run_scenario_analysis(panel, constraints, models)
    viz.plot_scenario_comparison(out["summary"])
    viz.plot_allocation_heatmap(
        out["baseline_result"].allocation, "Baseline optimal allocation (acres)", "allocation_baseline.png"
    )
    viz.plot_allocation_heatmap(
        out["adapted_result"].allocation, "Drought/heat optimal allocation (acres)", "allocation_drought_adapted.png"
    )
    viz.plot_allocation_shift(out["baseline_result"].allocation, out["adapted_result"].allocation)

    print("[4/4] Done.")
    print(out["summary"].to_string(index=False))
    print(
        f"Production saved by reallocation under drought/heat: "
        f"{out['production_saved_bu']:,.0f} bu ({out['production_saved_pct']:.2f}%)"
    )
    out["summary"].to_csv(viz.ROOT / "outputs" / "scenario_comparison.csv", index=False)


if __name__ == "__main__":
    main()
