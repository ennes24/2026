"""Stage 1 - crop yield prediction.

Trains and compares Random Forest, XGBoost, LightGBM, and (if installed)
CatBoost regressors per crop, with k-fold cross-validated hyperparameter
search and a held-out, time-based test split (train on years through
``TEST_YEAR_CUTOFF``, test on later years) to mimic real forecasting use.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, RandomizedSearchCV
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor

try:
    from catboost import CatBoostRegressor

    HAS_CATBOOST = True
except ImportError:  # pragma: no cover - optional dependency
    HAS_CATBOOST = False

from src.data_loader import feature_columns, load_or_build_processed

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "outputs" / "models"
TEST_YEAR_CUTOFF = 2018  # train: years <= cutoff, test: years > cutoff

warnings.filterwarnings("ignore", category=UserWarning)


@dataclass
class TrainedModel:
    crop: str
    model_name: str
    estimator: object
    metrics: dict
    feature_importance: pd.Series


PARAM_GRIDS = {
    "random_forest": dict(
        estimator=RandomForestRegressor(random_state=42, n_jobs=1),
        param_distributions={
            "n_estimators": [150, 300, 450],
            "max_depth": [4, 6, 8, None],
            "min_samples_leaf": [1, 2, 4],
            "max_features": ["sqrt", 0.8, 1.0],
        },
    ),
    "xgboost": dict(
        estimator=XGBRegressor(random_state=42, n_jobs=1, objective="reg:squarederror"),
        param_distributions={
            "n_estimators": [150, 300, 450],
            "max_depth": [3, 4, 6],
            "learning_rate": [0.03, 0.05, 0.1],
            "subsample": [0.7, 0.85, 1.0],
            "colsample_bytree": [0.7, 0.85, 1.0],
        },
    ),
    "lightgbm": dict(
        estimator=LGBMRegressor(random_state=42, n_jobs=1, verbosity=-1),
        param_distributions={
            "n_estimators": [150, 300, 450],
            "max_depth": [3, 4, 6, -1],
            "learning_rate": [0.03, 0.05, 0.1],
            "num_leaves": [15, 31, 63],
            "subsample": [0.7, 0.85, 1.0],
        },
    ),
}

if HAS_CATBOOST:
    PARAM_GRIDS["catboost"] = dict(
        estimator=CatBoostRegressor(random_state=42, verbose=False, thread_count=1),
        param_distributions={
            "iterations": [150, 300, 450],
            "depth": [4, 6, 8],
            "learning_rate": [0.03, 0.05, 0.1],
            "l2_leaf_reg": [1, 3, 5],
        },
    )


def _time_split(df: pd.DataFrame, cutoff: int = TEST_YEAR_CUTOFF):
    train = df[df["year"] <= cutoff]
    test = df[df["year"] > cutoff]
    return train, test


def _evaluate(y_true, y_pred) -> dict:
    return {
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
    }


def train_crop_models(panel: pd.DataFrame, crop: str, n_iter: int = 12, cv_splits: int = 5):
    """Tune + fit every candidate model for one crop; return per-model
    results plus the best model by test RMSE."""
    cols = feature_columns()
    data = panel[panel["crop"] == crop].dropna(subset=cols + ["yield_bu_acre"])
    train, test = _time_split(data)

    X_train, y_train = train[cols], train["yield_bu_acre"]
    X_test, y_test = test[cols], test["yield_bu_acre"]

    cv = KFold(n_splits=cv_splits, shuffle=True, random_state=42)
    results: dict[str, TrainedModel] = {}

    for name, spec in PARAM_GRIDS.items():
        search = RandomizedSearchCV(
            estimator=spec["estimator"],
            param_distributions=spec["param_distributions"],
            n_iter=n_iter,
            cv=cv,
            scoring="neg_root_mean_squared_error",
            random_state=42,
            n_jobs=-1,
        )
        search.fit(X_train, y_train)
        best = search.best_estimator_
        y_pred = best.predict(X_test)
        metrics = _evaluate(y_test, y_pred)
        metrics["cv_rmse"] = float(-search.best_score_)
        metrics["best_params"] = search.best_params_

        importances = getattr(best, "feature_importances_", np.zeros(len(cols)))
        fi = pd.Series(importances, index=cols).sort_values(ascending=False)

        results[name] = TrainedModel(crop, name, best, metrics, fi)

    best_name = min(results, key=lambda k: results[k].metrics["rmse"])
    return results, best_name


def train_all_crops(panel: pd.DataFrame | None = None, save: bool = True):
    panel = panel if panel is not None else load_or_build_processed()[0]
    crops = sorted(panel["crop"].unique())

    all_results = {}
    comparison_rows = []
    for crop in crops:
        results, best_name = train_crop_models(panel, crop)
        all_results[crop] = {"results": results, "best": best_name}
        for name, tm in results.items():
            comparison_rows.append(
                {
                    "crop": crop,
                    "model": name,
                    "rmse": tm.metrics["rmse"],
                    "mae": tm.metrics["mae"],
                    "r2": tm.metrics["r2"],
                    "cv_rmse": tm.metrics["cv_rmse"],
                    "is_best": name == best_name,
                }
            )
        if save:
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            joblib.dump(results[best_name].estimator, MODELS_DIR / f"{crop}_best_model.joblib")

    comparison = pd.DataFrame(comparison_rows).sort_values(["crop", "rmse"])
    if save:
        comparison.to_csv(ROOT / "outputs" / "model_comparison.csv", index=False)
    return all_results, comparison


def load_best_models(crops: list[str] | None = None) -> dict[str, object]:
    crops = crops or ["corn", "soybean", "wheat"]
    return {c: joblib.load(MODELS_DIR / f"{c}_best_model.joblib") for c in crops}


if __name__ == "__main__":
    panel_df, _ = load_or_build_processed()
    results_by_crop, comparison_df = train_all_crops(panel_df)
    pd.set_option("display.width", 120)
    print(comparison_df.to_string(index=False))
