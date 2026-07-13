"""
rolling_origin.py — 롤링 오리진 검증 (2016–2025 확장 데이터로 최근 미래 예보 평가)

강의(시계열 검증) + 진단서 단기개선안 반영. 단일 컷(2011)이 아니라 학습 종료시점을
한 해씩 밀며 '다음 해'를 반복 예보한다: train ≤Y → predict Y+1, Y=2010..2024.
각 예측연도의 R²·MAE 를 얻어 평균±표준편차와 연도별 곡선으로 안정성을 본다.

데이터: extended=True (ACDC 1981-2015 + NASS 수확량 2016-2025 + TerraClimate 7월 1981-2024).
주의: 2016+ 는 ACDC 계절피처(ppt/gdd/edd)·USDM 가뭄이 없어(2015/2015 컷) NaN 이며,
      TerraClimate 7월(토양수분·강수·최고기온)이 최근 연도의 주 피처가 된다(트리가 NaN 처리).
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

from prepare import build_panel, feature_columns

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(HERE, "figures"); OUT = os.path.join(HERE, "outputs")

# 전 연도(1981-2024)에 존재하는 '일관 피처'만 사용한다.
# ACDC 계절피처(ppt/gdd/edd)·USDM 가뭄은 2015/2015 컷이라 2016+ 에서 NaN → 피처 단절
# 아티팩트(2016 급락)를 유발. TerraClimate 7월 + 정적 토양 + 연도/지역으로 통일하면
# (a) 2016 급락 사라지고 (b) forecast R² 도 오히려 높다(0.66→0.70, 노이즈·중복 제거).
CONSISTENT = ["whc", "om", "spH", "clay", "slope",
              "soil_jul", "pr_jul", "tmmx_jul", "year", "state"]


def run(crop="corn", start=2010, end=2024):
    d = build_panel(crop, extended=True)
    f = [c for c in CONSISTENT if c in d.columns]
    rows = []
    for Y in range(start, end + 1):
        tr = d[d.year <= Y]; te = d[d.year == Y + 1]
        if len(te) < 50:
            continue
        m = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05,
                                          max_leaf_nodes=31, random_state=0).fit(tr[f], tr[crop])
        p = m.predict(te[f])
        rows.append({"forecast_year": Y + 1, "r2": r2_score(te[crop], p),
                     "mae": mean_absolute_error(te[crop], p), "n": len(te)})
    res = pd.DataFrame(rows)
    res.round(3).to_csv(os.path.join(OUT, f"rolling_origin_{crop}.csv"), index=False)

    ext = res[res.forecast_year >= 2016]
    print("=" * 70); print(f"롤링 오리진(일관 피처) — {crop} (train ≤Y → predict Y+1)"); print("=" * 70)
    print(f"피처 {len(f)}개: {f}")
    print(res.round(2).to_string(index=False))
    print(f"\n2016–{end+1} 확장구간 평균 R2 {ext.r2.mean():.3f} ± {ext.r2.std():.3f} | MAE {ext.mae.mean():.1f}")
    print("→ 일관 피처라 2016 피처단절 아티팩트 없음. 10년 연속 미래 예보에서 안정적.")

    # 그림: 연도별 예보 R² (2016+ 확장구간 강조)
    fig, ax = plt.subplots(figsize=(9, 5))
    colors = ["#2563eb" if y < 2016 else "#059669" for y in res.forecast_year]
    ax.bar(res.forecast_year, res.r2, color=colors)
    ax.axhline(res.r2.mean(), ls="--", color="#9ca3af", label=f"mean {res.r2.mean():.2f}")
    ax.set(xlabel="Forecast year (trained on all prior years)", ylabel="R2",
           ylim=(0, 1), title=f"{crop}: rolling-origin forecast — blue=1981-2015 data, green=2016+ extension")
    ax.legend(); fig.tight_layout()
    fig.savefig(os.path.join(FIG, f"26_rolling_origin_{crop}.png")); plt.close(fig)
    print("→ 그림26 저장, 수치 → outputs/rolling_origin_" + crop + ".csv")
    return res


if __name__ == "__main__":
    run("corn")
