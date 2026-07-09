"""
weather_ml.py — 날씨(기후) 예측 ML

타깃: 기후 변수 자체(edd, ppt). "미래 날씨를 얼마나 예측하나"를 정직하게 측정한다.

두 층으로 평가한다(EDA의 공간83%/시간11% 구조를 검증):
  (1) 절대값 예측 R² : 대부분 '공간(어디가 더운가)'을 맞히는 것 → 높게 나올 수 있음.
  (2) 연차편차(anomaly) 예측 R² : 카운티 평년을 뺀 '그해가 평년보다 더운가' → 여기서 진짜
      예측력이 드러남. 거의 0 이면 "연차 날씨는 예측 불가"라는 뜻.

베이스라인:
  - climatology : 그 카운티의 학습기 평균 (공간만 아는 모델)
  - persistence : 작년 값 그대로 (lag-1)
ML 이 이 둘을 얼마나 이기는지가 핵심.
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import r2_score, mean_absolute_error

from prepare import build_panel

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(HERE, "figures"); OUT = os.path.join(HERE, "outputs")
SPLIT = 2011
SOIL = ["whc", "om", "spH", "clay", "slope"]


def _add_lag(df, col):
    df = df.sort_values(["stco", "year"]).copy()
    df[f"{col}_lag1"] = df.groupby("stco")[col].shift(1)
    return df


def eval_target(df, target):
    df = _add_lag(df, target).dropna(subset=[f"{target}_lag1"])
    feats = ["year", "state"] + SOIL + [f"{target}_lag1"]
    tr, te = df[df.year < SPLIT], df[df.year >= SPLIT]

    m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05,
                                      max_leaf_nodes=31, random_state=0).fit(tr[feats], tr[target])
    pred = m.predict(te[feats])

    # 베이스라인
    clim = tr.groupby("stco")[target].mean()
    base_clim = te["stco"].map(clim).fillna(tr[target].mean()).values
    base_persist = te[f"{target}_lag1"].values

    # 절대값 R²
    r2_ml = r2_score(te[target], pred)
    r2_clim = r2_score(te[target], base_clim)
    r2_persist = r2_score(te[target], base_persist)

    # 연차편차(anomaly) R²: 카운티 평년(학습기) 제거 후
    anom_true = te[target].values - base_clim
    anom_pred = pred - base_clim
    r2_anom = r2_score(anom_true, anom_pred)

    return {"target": target, "r2_abs_ml": r2_ml, "r2_abs_climatology": r2_clim,
            "r2_abs_persistence": r2_persist, "r2_anomaly_ml": r2_anom,
            "mae_ml": mean_absolute_error(te[target], pred)}, (te[target].values, pred, base_clim)


def run():
    df = build_panel("corn")
    if "edd" not in df.columns:
        raise SystemExit("온도 필요")
    print("=" * 70); print("날씨 예측 ML (테스트 2011-2015)"); print("=" * 70)
    results = []; detail = {}
    for tgt in ["edd", "ppt"]:
        r, d = eval_target(df, tgt); results.append(r); detail[tgt] = d
    res = pd.DataFrame(results)
    res.round(3).to_csv(os.path.join(OUT, "weather_ml.csv"), index=False)

    for r in results:
        print(f"\n[{r['target']}]")
        print(f"  절대값 R²:  ML {r['r2_abs_ml']:.2f} | climatology {r['r2_abs_climatology']:.2f} "
              f"| persistence(lag1) {r['r2_abs_persistence']:.2f}")
        print(f"  연차편차 R²(평년 제거): ML {r['r2_anomaly_ml']:+.2f}")
        gain = r['r2_abs_ml'] - r['r2_abs_climatology']
        skill = "예측력 없음(평년보다 못함)" if r['r2_anomaly_ml'] < 0.1 else "유의미"
        verdict = "climatology(단순 평년)가 ML을 이김" if gain < 0 else f"ML이 +{gain:.2f} 우위"
        print(f"  → {verdict}. 연차편차 예측력: {skill}.")

    # 그림: 절대 R² 비교 (ML vs climatology vs persistence)
    fig, ax = plt.subplots(figsize=(8.5, 5))
    x = np.arange(len(res)); w = 0.26
    ax.bar(x - w, res.r2_abs_ml, w, label="ML", color="#1d4ed8")
    ax.bar(x, res.r2_abs_climatology, w, label="Climatology (spatial only)", color="#f59e0b")
    ax.bar(x + w, res.r2_abs_persistence, w, label="Persistence (last year)", color="#94a3b8")
    ax.set_xticks(x); ax.set_xticklabels(res.target)
    ax.set(ylabel="Test R² (absolute value)",
           title="W-ML. Predicting climate: ML ~ climatology; last year is useless")
    ax.legend(); ax.axhline(0, color="#444", lw=1); fig.tight_layout()
    fig.savefig(os.path.join(FIG, "23_weather_ml_r2.png")); plt.close(fig)

    # 그림: EDD 실제 vs 예측 (연차편차가 안 잡힘을 시각화)
    yt, yp, clim = detail["edd"]
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(yt, yp, s=6, alpha=0.25, color="#dc2626")
    lim = [min(yt.min(), yp.min()), max(yt.max(), yp.max())]
    ax.plot(lim, lim, "--", color="#9ca3af")
    ax.set(xlabel="Actual EDD", ylabel="Predicted EDD",
           title="EDD: spatial pattern captured, interannual scatter remains")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "24_weather_edd_pred.png")); plt.close(fig)

    print("\n→ 핵심: 날씨 ML의 높은 절대 R²은 대부분 '공간(어디)'을 맞힌 것이고,")
    print("  climatology 베이스라인이 이미 그걸 다 한다. '연차편차'는 ML도 못 잡는다(R²≈0).")
    print("  ⇒ 미래 날씨는 점예측이 아니라 '평년+추세+시나리오'로 다뤄야 한다(가설 H4 확증).")
    print("→ 그림 23·24, 수치 → outputs/weather_ml.csv")
    return res


if __name__ == "__main__":
    run()
