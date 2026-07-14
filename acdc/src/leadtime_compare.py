"""
leadtime_compare.py — 개선②: '봄 예보(7월 날씨 없이)' vs '여름 예보(7월 날씨 있이)'.

지금 모델은 그해 7월 날씨(dsci_jul·tmmx_jul·pr_jul·soil_jul)를 알고 예측한다 = 관측 후.
현실의 사전 예보는 봄에 7월을 모른다. 두 피처셋으로 같은 롤링검증을 돌려 정직하게 비교:

  (A) 봄  : 7월 날씨 제외 (정적 토양 + 강수/온도 계절값 + year/state)
  (B) 여름: 7월 날씨 포함 (지금 모델)

'여름'이 '봄'보다 좋은 만큼이 곧 '7월 관측의 값어치'다. 그리고 '봄' 성능이 현실에서
쓸 수 있는 진짜 사전 예보 성능이다.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import r2_score, mean_squared_error
from prepare import build_panel

JULY = ["dsci_jul", "soil_jul", "pr_jul", "tmmx_jul"]   # 7월 관측 (봄엔 모름)
BASE = ["ppt", "whc", "om", "spH", "clay", "slope", "gdd", "edd", "year", "state"]
SETS = {"(A) 봄 예보 (7월 없이)": BASE,
        "(B) 여름 예보 (7월 있이)": BASE + JULY}


def _fit(X, y):
    return HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05,
                                         max_leaf_nodes=31, random_state=0).fit(X, y)


def roll(d, feats, crop, start, end):
    a, p = [], []
    for Y in range(start, end + 1):
        tr = d[d.year <= Y - 1]; te = d[d.year == Y]
        if len(te) < 50:
            continue
        f = [c for c in feats if tr[c].nunique(dropna=True) >= 2]
        pred = _fit(tr[f], tr[crop].values).predict(te[f])
        a.append(te[crop].values); p.append(pred)
    a = np.concatenate(a); p = np.concatenate(p)
    return a, p


def run(crop="corn", start=2005, end=2015):
    d = build_panel(crop, extended=False)
    print("=" * 70)
    print(f"리드타임 비교 — {crop} (롤링 {start}~{end})")
    print("=" * 70)
    res = {}
    for name, feats in SETS.items():
        a, p = roll(d, feats, crop, start, end)
        rmse = np.sqrt(mean_squared_error(a, p)); r2 = r2_score(a, p)
        res[name] = (rmse, r2, a, p)
        print(f"  {name:24s}  RMSE {rmse:.1f}  R2 {r2:.3f}")
    (rb, r2b, ab, pb) = res["(A) 봄 예보 (7월 없이)"]
    (rs, r2s, a_, p_) = res["(B) 여름 예보 (7월 있이)"]
    print(f"\n  → 7월 관측의 값어치: RMSE {rb-rs:+.1f} 개선, R2 {r2s-r2b:+.3f}")
    print(f"  → 현실 사전예보(봄)로 쓸 수 있는 정직한 성능: R2 {r2b:.3f}, RMSE {rb:.1f}")

    # 2012 극단해에서 각각 얼마나 놓치나
    d12 = d[d.year == 2012]
    print("\n[2012 대가뭄 — 봄 vs 여름 예보]")
    for name, feats in SETS.items():
        tr = d[d.year <= 2011]
        f = [c for c in feats if tr[c].nunique(dropna=True) >= 2]
        m = _fit(tr[f], tr[crop].values)
        pred = m.predict(d12[f])
        print(f"  {name:24s}  실제 {d12[crop].mean():.0f} vs 예측 {pred.mean():.0f} "
              f"(과대 {pred.mean()-d12[crop].mean():+.0f})")
    print("  → 봄엔 7월 폭염을 모르니 2012 붕괴를 더 못 봄. 여름 관측이 붕괴 신호를 준다.")
    return res


if __name__ == "__main__":
    run("corn")
