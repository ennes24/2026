"""
heat_timing_test.py — "온도 세밀함 vs 온도 타이밍" 실험 (2012 급락을 무엇이 잡는가)

질문: 일간/세밀한 온도로 2012 같은 급락을 예측할 수 있나?
검증 설계: train ≤2011 → predict 2012 (급락 해를 '한 번도 본 적 없는' 상태로 예보).
피처를 단계적으로 넣어 2012 예측오차(편향·RMSE)가 무엇에서 줄어드는지 본다.

  A  blind      : 정적 토양 + year + state (온도 전혀 없음)
  B  +edd       : 시즌 전체 극한더위 도일 ("며칠 더웠나" = 온도 세밀함/카운트)
  C  +tmmx_jul  : 7월(수분기) 최고기온 ("결정적 시기에 더웠나" = 타이밍)
  D  +둘 다

대조군으로 2015(시원한 해)도 같이 본다 — 타이밍 피처가 '더운 해만' 돕는지 확인.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import r2_score, mean_absolute_error

from prepare import build_panel

BASE = ["whc", "om", "spH", "clay", "slope", "soil_jul", "pr_jul", "year", "state"]
SETS = {
    "A blind":     BASE,
    "B +edd":      BASE + ["edd"],
    "C +tmmx_jul": BASE + ["tmmx_jul"],
    "D +both":     BASE + ["edd", "tmmx_jul"],
}


def eval_year(d, feats, Y, crop):
    tr = d[d.year <= Y - 1]
    te = d[d.year == Y].dropna(subset=[crop])
    f = [c for c in feats if c in d.columns]
    m = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05,
                                      max_leaf_nodes=31, random_state=0).fit(tr[f], tr[crop])
    p = m.predict(te[f])
    a = te[crop].values
    return {"bias": float(np.mean(p - a)), "rmse": float(np.sqrt(np.mean((p - a) ** 2))),
            "r2": r2_score(a, p), "mae": mean_absolute_error(a, p)}


def run(crop="corn"):
    d = build_panel(crop, extended=True)
    for Y, tag in [(2012, "폭염 급락"), (2015, "시원 (대조군)")]:
        print("=" * 72)
        print(f"{Y}년 예보  [{tag}]   (train ≤{Y-1} → predict {Y})   실제평균 "
              f"{d[d.year==Y][crop].mean():.0f} bu/ac")
        print("=" * 72)
        print(f"{'feature set':<14}{'bias':>8}{'RMSE':>8}{'MAE':>8}{'R2':>8}")
        base_rmse = None
        for name, feats in SETS.items():
            r = eval_year(d, feats, Y, crop)
            if base_rmse is None:
                base_rmse = r["rmse"]
            drmse = r["rmse"] - base_rmse
            mark = "" if name == "A blind" else f"  (RMSE {drmse:+.1f})"
            print(f"{name:<14}{r['bias']:>+8.1f}{r['rmse']:>8.1f}{r['mae']:>8.1f}{r['r2']:>8.2f}{mark}")
        print()


if __name__ == "__main__":
    run("corn")
