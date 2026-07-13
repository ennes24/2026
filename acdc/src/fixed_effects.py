"""
fixed_effects.py — 2원 고정효과 인과 모델: "더위가 진짜 원인인가"

예측 모델(트리)은 R²는 높지만 "토양 pH 같은 지역 대리변수"에 기대므로 인과 해석이
위험하다. 여기서는 카운티·연도 **고정효과**로 지역차(좋은 땅)와 그해 전국충격(기술추세
·전국 날씨)을 모두 걷어낸 뒤, 그래도 극한고온(edd)이 수확량을 낮추는지 본다.

within 변환: x_it - x̄_county - x̄_year + x̄_overall  (2원 고정효과와 동치)
이후 OLS. edd 계수가 음수·강한 유의면 "지역·연도를 통제해도 더위가 인과적으로 해롭다".
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from prepare import build_panel

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(HERE, "figures"); OUT = os.path.join(HERE, "outputs")
VARS = ["edd", "gdd", "ppt"]
LABEL = {"edd": "Extreme heat (EDD)", "gdd": "Beneficial heat (GDD)", "ppt": "Precip"}


def _demean(df, col):
    return (df[col] - df.groupby("stco")[col].transform("mean")
            - df.groupby("year")[col].transform("mean") + df[col].mean())


def run(crop="corn"):
    d = build_panel(crop).dropna(subset=VARS + [crop]).copy()
    y = _demean(d, crop).values
    X = np.column_stack([_demean(d, c).values for c in VARS])
    XtX = X.T @ X
    beta = np.linalg.solve(XtX, X.T @ y)
    resid = y - X @ beta
    n, k = X.shape
    dof = n - k - d.stco.nunique() - d.year.nunique()   # 고정효과 자유도 차감
    s2 = (resid @ resid) / dof
    se = np.sqrt(np.diag(s2 * np.linalg.inv(XtX)))
    tvals = beta / se

    print("=" * 70)
    print(f"2원 고정효과(카운티+연도) 인과 회귀 — {crop}")
    print("=" * 70)
    rows = []
    for c, b, s, t in zip(VARS, beta, se, tvals):
        print(f"  {LABEL[c]:22s} 계수 {b:+.4f}  (SE {s:.4f}, t={t:+.1f})")
        rows.append({"var": c, "coef": b, "se": s, "t": t})
    print(f"  관측 {n:,} | 카운티 {d.stco.nunique()} | 연도 {d.year.nunique()}")
    print("→ edd 계수 음수·강한 유의 = 지역(좋은 땅)·연도(전국충격)를 통제해도")
    print("  극한고온 1 도일 증가가 수확량을 낮춘다 = '상관'이 아니라 '인과' 증거.")
    pd.DataFrame(rows).round(4).to_csv(os.path.join(OUT, f"fixed_effects_{crop}.csv"), index=False)

    # 그림: 계수 ± 95%CI
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    colors = ["#dc2626" if b < 0 else "#059669" for b in beta]
    ax.barh([LABEL[c] for c in VARS], beta, xerr=1.96 * se, color=colors, alpha=0.85)
    ax.axvline(0, color="#111", lw=1)
    ax.set(xlabel=f"Effect on {crop} yield (bu/ac per unit), county+year fixed effects",
           title=f"{crop}: heat is causal after removing region & year effects (t(EDD)={tvals[0]:.0f})")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, f"25_fixed_effects_{crop}.png")); plt.close(fig)
    print("→ 그림25 저장, 수치 → outputs/fixed_effects_" + crop + ".csv")
    return rows


if __name__ == "__main__":
    run("corn")
