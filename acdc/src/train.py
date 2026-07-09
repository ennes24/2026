"""
train.py — 수확량 예측 모델 학습 + 정직한 성능 평가 + 해석(블랙박스 방지)

평가 철학
  1) 시간 분할: 2010년 이전 학습 / 2011~2015 테스트. 미래를 미리 안 보고
     '예보 상황'을 흉내 낸다(랜덤 분할은 미래 누수라 금지).
  2) 베이스라인 대비: '추세만 아는 모델'(연도·주 평균)보다 날씨·토양을 넣은
     모델이 얼마나 나아지는지로 데이터의 실제 기여를 측정.
  3) 해석: 순열 중요도 + 부분의존도(PDP)로 '모델이 뭘 근거로 예측하나'를 연다.
  4) 2012 스트레스 테스트: 최악의 가뭄해를 얼마나 맞히나 → 데이터 적합성 판정.
"""
from __future__ import annotations
import os, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance, partial_dependence
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from prepare import build_panel, feature_columns

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(HERE, "figures"); OUT = os.path.join(HERE, "outputs")
os.makedirs(FIG, exist_ok=True); os.makedirs(OUT, exist_ok=True)
SPLIT_YEAR = 2011  # 이 해부터 테스트


def time_split(df, feats, target):
    tr = df[df.year < SPLIT_YEAR]; te = df[df.year >= SPLIT_YEAR]
    return (tr[feats], tr[target], te[feats], te[target], tr, te)


def evaluate(y_true, y_pred):
    return {"rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
            "mae": float(mean_absolute_error(y_true, y_pred)),
            "r2": float(r2_score(y_true, y_pred))}


def trend_baseline(tr, te, target):
    """베이스라인: (주, 연도추세)만으로 예측. 날씨·토양 없이 얼마나 가나."""
    # 주별 선형추세를 학습셋에서 적합 → 테스트연도에 외삽
    pred = np.zeros(len(te))
    gmean = tr[target].mean()
    for st, idx in te.groupby("state").groups.items():
        sub = tr[tr.state == st]
        if len(sub) >= 10:
            b1, b0 = np.polyfit(sub.year, sub[target], 1)
            pred[te.index.get_indexer(idx)] = b0 + b1 * te.loc[idx, "year"]
        else:
            pred[te.index.get_indexer(idx)] = gmean
    return pred


def train_crop(crop="corn"):
    df = build_panel(crop)
    feats = feature_columns(df)
    Xtr, ytr, Xte, yte, tr, te = time_split(df, feats, crop)

    models = {
        "random_forest": RandomForestRegressor(n_estimators=300, min_samples_leaf=3,
                                                n_jobs=-1, random_state=0),
        "hist_gbm": HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05,
                                                  max_leaf_nodes=31, random_state=0),
    }
    results = {}
    preds = {}
    for name, m in models.items():
        m.fit(Xtr, ytr)
        p = m.predict(Xte)
        results[name] = evaluate(yte, p)
        preds[name] = p

    base_pred = trend_baseline(tr, te, crop)
    results["trend_baseline"] = evaluate(yte, base_pred)

    best = min([k for k in models], key=lambda k: results[k]["rmse"])
    best_model = models[best]
    best_pred = preds[best]

    # ---- 해석 1: 순열 중요도 ----
    pi = permutation_importance(best_model, Xte, yte, n_repeats=10,
                                random_state=0, n_jobs=-1)
    imp = pd.Series(pi.importances_mean, index=feats).sort_values()
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(imp.index, imp.values, color="#2563eb")
    ax.set(xlabel="Permutation importance (drop in R2 when shuffled)",
           title=f"{crop}: what the model actually uses ({best})")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, f"06_importance_{crop}.png")); plt.close(fig)

    # ---- 해석 2: 부분의존도 (강수) ----
    try:
        pd_ppt = partial_dependence(best_model, Xtr, ["ppt"], grid_resolution=40)
        xs = pd_ppt["grid_values"][0]; ys = pd_ppt["average"][0]
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(xs, ys, color="#059669")
        ax.set(xlabel="Growing-season precip (mm)", ylabel=f"Predicted {crop} yield (bu/ac)",
               title=f"{crop}: partial dependence on rainfall (model's learned response)")
        fig.tight_layout(); fig.savefig(os.path.join(FIG, f"07_pdp_ppt_{crop}.png")); plt.close(fig)
    except Exception as e:
        print("PDP skip:", e)

    # ---- 해석 3: 실제 vs 예측 (테스트연도) ----
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(yte, best_pred, s=6, alpha=0.25, color="#2563eb")
    lim = [min(yte.min(), best_pred.min()), max(yte.max(), best_pred.max())]
    ax.plot(lim, lim, "--", color="#9ca3af")
    ax.set(xlabel=f"Actual {crop} yield", ylabel="Predicted",
           title=f"{crop}: actual vs predicted (test 2011-2015, R2={results[best]['r2']:.2f})")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, f"08_actual_vs_pred_{crop}.png")); plt.close(fig)

    # ---- 2012 스트레스 테스트 (옥수수만 의미 큼) ----
    stress = {}
    if 2012 in te.year.values:
        m12 = te.year == 2012
        stress = {
            "actual_mean": float(yte[m12].mean()),
            "pred_mean": float(best_pred[m12].mean()),
            "trend_expect_mean": float(tr[crop].groupby(tr.state).mean().reindex(te[m12].state).mean()),
            "rmse_2012": float(np.sqrt(mean_squared_error(yte[m12], best_pred[m12]))),
        }

    out = {"crop": crop, "n_train": int(len(tr)), "n_test": int(len(te)),
           "features": feats, "has_temperature": "gdd" in df.columns,
           "best_model": best, "metrics": results, "importance": imp.to_dict(),
           "stress_2012": stress}
    with open(os.path.join(OUT, f"model_{crop}.json"), "w") as f:
        json.dump(out, f, indent=2)
    return out


def print_report(out):
    crop = out["crop"]; R = out["metrics"]; b = out["best_model"]
    print("=" * 70); print(f"모델 결과 — {crop}"); print("=" * 70)
    print(f"학습 {out['n_train']:,}행(≤2010) / 테스트 {out['n_test']:,}행(2011-2015)")
    print(f"온도 피처: {'있음' if out['has_temperature'] else '없음'}")
    print(f"{'모델':<18}{'RMSE':>8}{'MAE':>8}{'R2':>8}")
    for k, v in R.items():
        print(f"{k:<18}{v['rmse']:>8.1f}{v['mae']:>8.1f}{v['r2']:>8.2f}")
    lift = R["trend_baseline"]["rmse"] - R[b]["rmse"]
    print(f"\n→ 날씨·토양 추가로 RMSE {lift:+.1f} bu/ac 개선(추세만 대비).")
    imp = out["importance"]
    top = sorted(imp.items(), key=lambda x: -x[1])[:3]
    print("→ 가장 중요한 피처 top3:", ", ".join(f"{k}({v:.2f})" for k, v in top))
    s = out["stress_2012"]
    if s:
        print(f"\n[2012 가뭄 스트레스] 실제 {s['actual_mean']:.0f} / 예측 {s['pred_mean']:.0f} "
              f"bu/ac  (RMSE {s['rmse_2012']:.0f})")
        gap = s["pred_mean"] - s["actual_mean"]
        print(f"→ 모델이 2012를 {gap:+.0f} bu/ac 만큼 {'과대예측(가뭄 과소평가)' if gap>0 else '잘 잡음'}.")


if __name__ == "__main__":
    for crop in ("corn", "soybean"):
        print_report(train_crop(crop)); print()
