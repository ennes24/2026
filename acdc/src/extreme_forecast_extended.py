"""
extreme_forecast_extended.py — 개선①: 데이터를 2016~2025로 확장해 '최근'도 검증.

extreme_forecast.py 와 같은 방식(분위수 P10/P50/P90 + 컨포멀 보정)인데,
- extended=True 로 2016~2025 를 붙이고
- 전 연도(1981-2024)에 다 존재하는 '일관 피처'만 쓴다.
  (2016+ 에서 gdd/edd/ppt/dsci_jul 은 빈칸이라, 이걸 쓰면 최근 연도가 불공정해짐)

목적: "10년 전 데이터로 멈춘 모델"이 아니라 "최근 연도도 맞히는 모델"임을 보인다.
2025 는 TerraClimate 7월이 아직 없어(약 1년 지연) 제외, 2016~2024 로 검증.
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import r2_score, mean_squared_error
from prepare import build_panel

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "outputs")

# 전 연도(1981-2024)에 다 있는 피처만 (2016+ 에서 NaN 되는 계절피처 제외)
CONSISTENT = ["whc", "om", "spH", "clay", "slope",
              "soil_jul", "pr_jul", "tmmx_jul", "year", "state"]
QUANTILES = [0.1, 0.5, 0.9]


def _fit(kind, X, y, q=None):
    kw = dict(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, random_state=0)
    if kind == "quantile":
        return HistGradientBoostingRegressor(loss="quantile", quantile=q, **kw).fit(X, y)
    return HistGradientBoostingRegressor(loss="squared_error", **kw).fit(X, y)


def run(crop="corn", start=2010, end=2024, alpha=0.2):
    d = build_panel(crop, extended=True)
    f0 = [c for c in CONSISTENT if c in d.columns]
    rows = []
    for Y in range(start, end + 1):
        proper = d[d.year <= Y - 2]
        calib = d[d.year == Y - 1]
        te = d[d.year == Y].copy()
        if len(te) < 50 or len(calib) < 50:
            continue
        f = [c for c in f0 if proper[c].nunique(dropna=True) >= 2]
        Xp, yp = proper[f], proper[crop].values
        point = _fit("squared_error", Xp, yp).predict(te[f])
        m10 = _fit("quantile", Xp, yp, 0.1); m50 = _fit("quantile", Xp, yp, 0.5)
        m90 = _fit("quantile", Xp, yp, 0.9)
        yc = calib[crop].values
        E = np.maximum(m10.predict(calib[f]) - yc, yc - m90.predict(calib[f]))
        k = int(np.ceil((len(E) + 1) * (1 - alpha)))
        Q = np.sort(E)[min(k, len(E)) - 1]
        te["actual"] = te[crop].values
        te["point"] = point
        te["p10"] = m10.predict(te[f]) - Q
        te["p50"] = m50.predict(te[f])
        te["p90"] = m90.predict(te[f]) + Q
        rows.append(te[["stco", "year", "actual", "point", "p10", "p50", "p90"]])
    R = pd.concat(rows, ignore_index=True)
    R["p50"] = R[["p10", "p50"]].max(axis=1)
    R["p90"] = R[["p50", "p90"]].max(axis=1)
    R.to_csv(os.path.join(OUT, f"extreme_forecast_extended_{crop}.csv"), index=False)

    def yearly(g):
        cov = ((g.actual >= g.p10) & (g.actual <= g.p90)).mean() * 100
        return pd.Series({"n": len(g), "actual": g.actual.mean(),
                          "point_bias": (g.point - g.actual).mean(),
                          "p10": g.p10.mean(), "p90": g.p90.mean(),
                          "coverage": cov,
                          "RMSE": np.sqrt(mean_squared_error(g.actual, g.point))})
    yr = R.groupby("year").apply(yearly, include_groups=False).round(1)

    print("=" * 74)
    print(f"확장 검증 — {crop} (일관피처 {len(f0)}개, 2016~2024 = '최근' 미래예보)")
    print("=" * 74)
    print(yr.to_string())

    recent = R[R.year >= 2016]
    old = R[R.year < 2016]
    print("\n[옛날(≤2015) vs 최근(2016~2024) 비교]")
    for name, g in [("≤2015", old), ("2016~2024", recent)]:
        cov = ((g.actual >= g.p10) & (g.actual <= g.p90)).mean() * 100
        print(f"  {name:10s}  RMSE {np.sqrt(mean_squared_error(g.actual,g.point)):.1f}  "
              f"R2 {r2_score(g.actual,g.point):.3f}  커버리지 {cov:.1f}%")
    print("→ 최근 연도도 옛날과 비슷하면, 모델이 '지금'도 작동한다는 증거.")
    return R, yr


if __name__ == "__main__":
    run("corn")
