"""
weather_eda.py — 날씨(기후) 예측용 EDA

수확량이 아니라 '기후 변수(edd·gdd·ppt) 자체'를 타깃으로 볼 때의 탐색.
핵심 질문: 미래 날씨를 예측할 수 있는가? → 데이터가 답한다.

그림:
  W1. 기후 변수 분포 (climatology)
  W2. 분산분해: 공간(어디) vs 시간(언제) — 어느 쪽이 지배하나
  W3. 연도 추세 (warming hole 재확인)
  W4. lag-1 자기상관: 작년 날씨로 올해를 맞힐 수 있나
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
FIG = os.path.join(HERE, "figures")
plt.rcParams.update({"figure.dpi": 110, "font.size": 11, "axes.grid": True, "grid.alpha": 0.3})
VARS = ["edd", "gdd", "ppt"]
LABEL = {"edd": "EDD (extreme heat)", "gdd": "GDD (beneficial heat)", "ppt": "Precip (mm)"}


def var_decomp(df, col):
    """전체 분산 중 공간(카운티간)·시간(연도간)·잔차 비중."""
    grand = df[col].mean()
    cty = df.groupby("stco")[col].transform("mean")
    yr = df.groupby("year")[col].transform("mean")
    ss_tot = ((df[col] - grand) ** 2).sum()
    ss_space = ((cty - grand) ** 2).sum()
    ss_time = ((yr - grand) ** 2).sum()
    return ss_space / ss_tot, ss_time / ss_tot


def run():
    df = build_panel("corn")
    if "edd" not in df.columns:
        raise SystemExit("온도 필요")
    print("=" * 70); print("날씨 예측 EDA"); print("=" * 70)

    # W1 분포
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for ax, c in zip(axes, VARS):
        ax.hist(df[c], bins=50, color="#0ea5e9", alpha=0.8)
        ax.set(title=LABEL[c], ylabel="count")
    fig.suptitle("W1. Climate variable distributions (climatology)")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "W1_climate_dist.png")); plt.close(fig)

    # W2 분산분해
    rows = []
    for c in VARS:
        s, t = var_decomp(df, c)
        rows.append((c, s, t, 1 - s - t))
    dec = pd.DataFrame(rows, columns=["var", "space", "time", "resid"])
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(dec["var"], dec.space, label="Space (which county)", color="#1d4ed8")
    ax.bar(dec["var"], dec.time, bottom=dec.space, label="Time (which year)", color="#f59e0b")
    ax.bar(dec["var"], dec.resid, bottom=dec.space + dec.time, label="Residual (local·yr)", color="#cbd5e1")
    ax.set(ylabel="Share of total variance",
           title="W2. Climate variance is mostly SPATIAL — the year matters little")
    ax.legend(); fig.tight_layout()
    fig.savefig(os.path.join(FIG, "W2_variance_decomp.png")); plt.close(fig)
    print("\n[W2 분산분해] 공간(어디) vs 시간(언제):")
    for _, r in dec.iterrows():
        print(f"  {r['var']}: 공간 {r.space:.0%} / 시간 {r.time:.0%} / 잔차 {r.resid:.0%}")

    # W3 연도추세
    yrm = df.groupby("year")[VARS].mean()
    fig, ax = plt.subplots(figsize=(9, 5))
    for c, col in zip(VARS, ["#dc2626", "#16a34a", "#0ea5e9"]):
        z = (yrm[c] - yrm[c].mean()) / yrm[c].std()
        ax.plot(yrm.index, z, "o-", ms=3, color=col, label=c)
    ax.axhline(0, color="#9ca3af", lw=1)
    ax.set(xlabel="Year", ylabel="Standardized anomaly",
           title="W3. Trends: EDD flat/down (warming hole), precip up")
    ax.legend(); fig.tight_layout()
    fig.savefig(os.path.join(FIG, "W3_year_trend.png")); plt.close(fig)

    # W4 lag-1 자기상관
    ac = {}
    for c in VARS:
        piv = df.pivot_table(index="year", columns="stco", values=c)
        ac[c] = piv.corrwith(piv.shift(1)).mean()
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(list(ac.keys()), list(ac.values()), color="#7c3aed")
    for i, v in enumerate(ac.values()):
        ax.text(i, v, f"{v:.2f}", ha="center", va="bottom")
    ax.axhline(0, color="#9ca3af", lw=1); ax.set_ylim(-0.1, 1)
    ax.set(ylabel="Lag-1 autocorrelation",
           title="W4. Last year barely predicts this year -> weather is not forecastable here")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "W4_autocorr.png")); plt.close(fig)
    print("\n[W4 자기상관] 작년→올해 예측력:")
    for c, v in ac.items():
        print(f"  {c}: lag-1 corr {v:.3f}")
    print("\n→ 결론: 기후는 '어디(공간)'로는 잘 설명되지만 '언제(연도)'는 거의 예측 불가.")
    print("  → 날씨 ML은 기후평년(climatology)+추세만 잡고, 연차 변동은 못 잡는다 → 시나리오로 다뤄야(H4).")
    return dec


if __name__ == "__main__":
    run()
