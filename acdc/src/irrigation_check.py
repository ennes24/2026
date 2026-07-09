"""
irrigation_check.py — '관개가 기상충격 변동성을 낮추는가' 실데이터 검증

배경: 이전 리포트에서 "NE가 안정적인 건 관개 때문"이라고 배경지식으로 단정했다.
이제 USDA NASS Census 2012 카운티 관개비율(irrigation_slim.csv)로 실제 검증한다.

결론(실데이터): NE는 관개 1위(≈54%)이자 변동성 최저 — 그 한 곳은 설명이 맞다.
그러나 관개↔변동성 상관은 약하다(주단위 r≈-0.08, 카운티 r≈-0.13). TX·KS는 관개가
높아도 변동성이 크다. 즉 '관개가 변동성을 낮춘다'는 약한 경향은 있으나 일반 법칙은 아니다.
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from prepare import build_panel, DATA

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(HERE, "figures"); OUT = os.path.join(HERE, "outputs")


def run():
    irr_path = os.path.join(DATA, "irrigation_slim.csv")
    if not os.path.exists(irr_path):
        print("irrigation_slim.csv 없음 — tools/prep_irrigation.py 로 먼저 생성."); return
    irr = pd.read_csv(irr_path)
    d = build_panel("corn").merge(irr, on="stco", how="left")

    # 주 단위
    st = (d.groupby("state_abbr")
          .agg(irrig=("irrig_share", "mean"),
               vol=("corn_anom_pct", lambda x: x.std()))
          .dropna().sort_values("irrig", ascending=False))
    r_state = st.irrig.corr(st.vol)

    # 카운티 단위 (표본 충분한 곳만)
    cty = (d.groupby("stco")
           .agg(irrig=("irrig_share", "first"),
                vol=("corn_anom_pct", lambda x: x.std()),
                n=("corn_anom_pct", "size")).dropna())
    cty = cty[cty.n >= 15]
    r_cty = cty.irrig.corr(cty.vol)

    print("=" * 70); print("관개 vs 기상충격 변동성 — 실데이터 검증 (NASS 2012)"); print("=" * 70)
    print(st.round(3).to_string())
    print(f"\n주단위 상관 r = {r_state:.3f}  |  카운티단위(n>=15) r = {r_cty:.3f} (카운티 {len(cty)}개)")
    print("→ NE: 관개 1위(54%)·변동성 최저 — 그 한 곳은 설명 일치.")
    print("→ 그러나 상관이 약하고 TX·KS(관개 높음·변동성 높음)가 반례 → '관개=안정'은 일반화 불가.")

    st.round(4).to_csv(os.path.join(OUT, "irrigation_vs_volatility.csv"))

    # 그림: 주별 관개비율 vs 변동성 산점도 (NE 강조)
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    ax.scatter(st.irrig * 100, st.vol, s=60, color="#2563eb", zorder=3)
    for name, row in st.iterrows():
        ax.annotate(name, (row.irrig * 100, row.vol), textcoords="offset points",
                    xytext=(5, 3), fontsize=9,
                    color="#b91c1c" if name in ("NE", "TX", "KS", "SD") else "#444")
    # 추세선
    b1, b0 = np.polyfit(st.irrig * 100, st.vol, 1)
    xs = np.linspace(0, st.irrig.max() * 100, 20)
    ax.plot(xs, b0 + b1 * xs, "--", color="#9ca3af",
            label=f"trend (state r={r_state:.2f}, weak)")
    ax.set(xlabel="Irrigation share of corn area (%, NASS 2012)",
           ylabel="Weather-shock volatility (std of yield anomaly %)",
           title="Irrigation vs volatility: NE fits, but the overall link is weak (TX/KS don't)")
    ax.legend(); fig.tight_layout()
    fig.savefig(os.path.join(FIG, "23_irrigation_vs_volatility.png")); plt.close(fig)
    print("→ 그림23 저장, 수치 → outputs/irrigation_vs_volatility.csv")
    return st


if __name__ == "__main__":
    run()
