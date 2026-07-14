"""
extreme_coverage_fix.py — 개선③: 극단해에서 구간 커버리지를 높인다(특히 하방).

문제: 전체 커버리지는 80%인데 극단해(2012)는 64~77%. 붕괴 경고가 목표인데 붕괴 때 약함.
원인: 컨포멀 보정 폭 Q 가 '평범한 해' 기준이라, 붕괴엔 하방이 모자란다.

세 방식 비교(롤링 2005-2015):
  (기본)   대칭 컨포멀: p10-Q, p90+Q  (지금 방식)
  (A) 하방강화: 하방만 더 넓게 — p10 -= Q*beta (beta>1), p90 += Q
  (B) 하방분위: 보정량을 '하방 실수(E_low)'의 더 높은 분위수로 잡아 꼬리에 대비

평가: 전체 커버리지는 80% 유지하면서, '극단해 하방'을 얼마나 더 담나(하방 커버리지).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_squared_error
from prepare import build_panel

FEATS = ["ppt", "whc", "om", "spH", "clay", "slope", "year", "state",
         "gdd", "edd", "dsci_jul", "soil_jul", "pr_jul", "tmmx_jul"]


def _fit(X, y, q=None):
    kw = dict(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, random_state=0)
    if q is None:
        return HistGradientBoostingRegressor(loss="squared_error", **kw).fit(X, y)
    return HistGradientBoostingRegressor(loss="quantile", quantile=q, **kw).fit(X, y)


def run(crop="corn", start=2005, end=2015, alpha=0.2):
    d = build_panel(crop, extended=False)
    rows = []
    for Y in range(start, end + 1):
        proper = d[d.year <= Y - 2]; calib = d[d.year == Y - 1]; te = d[d.year == Y].copy()
        if len(te) < 50 or len(calib) < 50:
            continue
        f = [c for c in FEATS if proper[c].nunique(dropna=True) >= 2]
        Xp, yp = proper[f], proper[crop].values
        m10 = _fit(Xp, yp, 0.1); m50 = _fit(Xp, yp, 0.5); m90 = _fit(Xp, yp, 0.9)

        yc = calib[crop].values
        lo_c = m10.predict(calib[f]); hi_c = m90.predict(calib[f])
        # 대칭 보정량(기본): 양방향 실수의 (1-alpha) 분위수
        E = np.maximum(lo_c - yc, yc - hi_c)
        Q = np.sort(E)[min(int(np.ceil((len(E) + 1) * (1 - alpha))), len(E)) - 1]
        # 하방 실수만: 실제가 P10 아래로 벗어난 양 (붕괴 대비)
        Elow = np.maximum(lo_c - yc, 0)
        Qlow = np.sort(Elow)[min(int(np.ceil((len(Elow) + 1) * (1 - alpha / 2))), len(Elow)) - 1]

        p10 = m10.predict(te[f]); p90 = m90.predict(te[f])
        te["actual"] = te[crop].values
        te["p10_base"] = p10 - Q;          te["p90_base"] = p90 + Q
        te["p10_A"] = p10 - Q * 1.5;       te["p90_A"] = p90 + Q      # 하방 1.5배
        te["p10_B"] = p10 - Qlow;          te["p90_B"] = p90 + Q      # 하방 별도분위
        rows.append(te[["stco", "year", "actual",
                        "p10_base", "p90_base", "p10_A", "p90_A", "p10_B", "p90_B"]])
    R = pd.concat(rows, ignore_index=True)

    # 극단해 판정(추세 제거 후 하위 20%)
    ym = R.groupby("year").actual.mean()
    b1, b0 = np.polyfit(ym.index.values, ym.values, 1)
    ext_years = ym.index[(ym.values - (b0 + b1 * ym.index.values)) <=
                         np.quantile(ym.values - (b0 + b1 * ym.index.values), 0.2)]

    def cov(g, lo, hi):
        return ((g.actual >= g[lo]) & (g.actual <= g[hi])).mean() * 100

    def below(g, lo):   # 하방 커버리지: 실제가 P10 위(=하방이 안 뚫림)
        return (g.actual >= g[lo]).mean() * 100

    def width(g, lo, hi):
        return (g[hi] - g[lo]).mean()

    ext = R[R.year.isin(ext_years)]
    print("=" * 74)
    print(f"극단해 커버리지 개선 — {crop} (극단해: {list(ext_years)})")
    print("=" * 74)
    print(f"{'방식':<16}{'전체커버':>10}{'극단커버':>10}{'극단하방OK':>12}{'평균폭':>9}")
    for tag, lo, hi in [("기본(대칭)", "p10_base", "p90_base"),
                        ("A 하방1.5배", "p10_A", "p90_A"),
                        ("B 하방분위", "p10_B", "p90_B")]:
        print(f"{tag:<16}{cov(R,lo,hi):>9.1f}%{cov(ext,lo,hi):>9.1f}%"
              f"{below(ext,lo):>11.1f}%{width(R,lo,hi):>9.0f}")
    print("\n  '극단하방OK' = 극단해에 실제가 하방(P10) 위에 있던 비율 = 붕괴를 구간이 담은 정도")
    print("  → 하방을 넓히면 극단해 커버리지·하방보호가 오르지만, 평균 폭도 커진다(트레이드오프).")

    # 2012 하방이 실제(109)를 담나
    g12 = R[R.year == 2012]
    print(f"\n[2012] 실제 {g12.actual.mean():.0f} | 하방 P10 —  "
          f"기본 {g12.p10_base.mean():.0f} / A {g12.p10_A.mean():.0f} / B {g12.p10_B.mean():.0f}")
    print(f"       2012 하방보호(실제≥P10) —  기본 {below(g12,'p10_base'):.0f}% / "
          f"A {below(g12,'p10_A'):.0f}% / B {below(g12,'p10_B'):.0f}%")
    return R


if __name__ == "__main__":
    run("corn")
