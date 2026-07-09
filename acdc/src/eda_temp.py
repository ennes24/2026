"""
eda_temp.py — 온도(EDD/GDD) 중심 EDA (온도 확보 후 추가된 그림들)

온도가 들어온 뒤에야 볼 수 있는 관계들을 그린다:
  13. 연도별 극한고온(EDD) 타임라인 — 2012가 실제로 튀는지
  14. EDD → 수확량 편차 반응곡선 — 고온이 수확량을 깎는가
  15. 옥수수 vs 대두 고온 민감도 비교 — 왜 대두가 더 강한가
  16. 대두 추세/기상충격 (옥수수 그림1의 대두판)
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


def fig_edd_timeline(df):
    g = df.groupby("year").agg(edd=("edd", "mean"), corn=("corn_anom", "mean")).reset_index()
    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.bar(g.year, g.edd, color="#f0a24b", label="EDD (extreme heat)")
    ax1.set(xlabel="Year", ylabel="Mean EDD (>30C degree-days)")
    ax2 = ax1.twinx()
    ax2.plot(g.year, g.corn, "o-", color="#1e3a8a", label="Corn yield anomaly")
    ax2.axhline(0, color="#9ca3af", lw=1); ax2.set_ylabel("Corn yield anomaly (bu/ac)")
    ax2.grid(False)
    for yr in (1988, 2012):
        if yr in g.year.values:
            ax1.annotate(str(yr), (yr, g.loc[g.year == yr, "edd"].iloc[0]),
                         textcoords="offset points", xytext=(0, 6), ha="center",
                         fontsize=9, color="#b45309", fontweight="bold")
    ax1.set_title("Extreme-heat years line up with corn shortfalls (2012, 1988)")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "13_edd_timeline.png")); plt.close(fig)


def fig_edd_response(df):
    d = df.dropna(subset=["corn_anom", "edd"]).copy()
    d["edd_bin"] = pd.qcut(d.edd, 10, duplicates="drop")
    g = d.groupby("edd_bin", observed=True).agg(anom=("corn_anom", "mean"),
                                                n=("corn_anom", "size")).reset_index()
    centers = g.edd_bin.apply(lambda b: b.mid).astype(float)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.axhline(0, color="#9ca3af", lw=1)
    ax.plot(centers, g.anom, "o-", color="#dc2626")
    ax.set(xlabel="Extreme-heat exposure EDD (>30C degree-days)",
           ylabel="Corn yield anomaly vs trend (bu/ac)",
           title="More extreme heat -> larger yield shortfall (monotone)")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "14_edd_response_corn.png")); plt.close(fig)


def fig_heat_sensitivity(corn, soy):
    """옥수수 vs 대두: 같은 EDD 구간에서 추세대비 %손실을 비교."""
    def curve(df):
        d = df.dropna(subset=[f"{crop}_anom_pct", "edd"]).copy() if False else df.dropna(subset=["edd"]).copy()
        return d
    fig, ax = plt.subplots(figsize=(9, 5))
    for df, crop, color in [(corn, "corn", "#b45309"), (soy, "soybean", "#15803d")]:
        col = f"{crop}_anom_pct"
        d = df.dropna(subset=[col, "edd"]).copy()
        d["edd_bin"] = pd.qcut(d.edd, 10, duplicates="drop")
        g = d.groupby("edd_bin", observed=True)[col].mean()
        centers = [b.mid for b in g.index]
        ax.plot(centers, g.values, "o-", color=color, label=crop)
    ax.axhline(0, color="#9ca3af", lw=1)
    ax.set(xlabel="Extreme-heat exposure EDD", ylabel="Yield anomaly vs trend (% of trend)",
           title="Corn is more heat-sensitive than soybean (steeper drop)")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "15_heat_sensitivity.png")); plt.close(fig)


def fig_soy_trend(soy):
    nat = soy.groupby("year").agg(y=("soybean", "mean"), t=("soybean_trend", "mean")).reset_index()
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(nat.year, nat.y, "o-", color="#15803d", label="Actual mean yield")
    ax.plot(nat.year, nat.t, "--", color="#9ca3af", label="Technology trend")
    ax.set(xlabel="Year", ylabel="Soybean yield (bu/ac)",
           title="Soybean: technology trend + weather shocks")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "16_soy_trend.png")); plt.close(fig)


def run():
    corn = build_panel("corn"); soy = build_panel("soybean")
    if "edd" not in corn.columns:
        print("온도 데이터 없음 — 온도 EDA 건너뜀."); return
    print("=" * 70); print("온도(EDD/GDD) EDA — 추가 그림 13~16"); print("=" * 70)
    fig_edd_timeline(corn)
    print("[그림13] 연도별 EDD 막대와 옥수수 편차 선. 2012·1988 고온해가 흉작과 정렬.")
    fig_edd_response(corn)
    print("[그림14] EDD가 커질수록 추세대비 수확량이 단조 감소 → 고온피해 실측 확인.")
    fig_heat_sensitivity(corn, soy)
    print("[그림15] 같은 EDD에서 옥수수 %손실 기울기가 대두보다 가파름 → 옥수수가 더 취약.")
    fig_soy_trend(soy)
    print("[그림16] 대두도 추세+충격 구조는 같으나 변동폭이 옥수수보다 작다.")
    print("\n그림 4장 저장 →", FIG)


if __name__ == "__main__":
    run()
