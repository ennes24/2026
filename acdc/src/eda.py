"""
eda.py — 탐색적 데이터 분석 (그림 + 설명 출력)

블랙박스를 피하는 게 목표다. 각 그림이 '무엇을 보여주고 무엇을 뜻하는지'를
콘솔에 함께 출력한다. 그림의 축 라벨은 영어(matplotlib 한글 폰트 이슈 회피),
해석은 REPORT.md 와 콘솔 출력에서 한국어로 설명한다.
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from prepare import build_panel, feature_columns, CORN_BELT_FIPS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)
plt.rcParams.update({"figure.dpi": 110, "font.size": 11, "axes.grid": True,
                     "grid.alpha": 0.3, "axes.spikes.top" if False else "axes.edgecolor": "#444"})

DROUGHTS = {1983: "1983", 1988: "1988 heat/drought", 1993: "1993 flood",
            2012: "2012 mega-drought"}


def fig_trend_and_shocks(df: pd.DataFrame):
    """그림1: 기술추세 vs 기상충격 — 이 프로젝트의 핵심 관점."""
    nat = df.groupby("year").agg(yield_mean=("corn", "mean"),
                                 trend_mean=("corn_trend", "mean")).reset_index()
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(nat.year, nat.yield_mean, "o-", color="#2563eb", label="Actual mean yield")
    ax.plot(nat.year, nat.trend_mean, "--", color="#9ca3af", label="Technology trend (county fits)")
    for yr, lab in DROUGHTS.items():
        if yr in nat.year.values:
            v = nat.loc[nat.year == yr, "yield_mean"].iloc[0]
            ax.annotate(lab, (yr, v), textcoords="offset points", xytext=(0, -28),
                        ha="center", fontsize=8.5, color="#b91c1c",
                        arrowprops=dict(arrowstyle="->", color="#b91c1c", lw=1))
    ax.set(xlabel="Year", ylabel="Corn yield (bu/ac)",
           title="Corn yield = steady technology trend + year-to-year weather shocks")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "01_trend_and_shocks.png")); plt.close(fig)
    return nat


def fig_precip_response(df: pd.DataFrame):
    """그림2: 강수 → 수확량 반응 곡선. 추세를 제거한 '기상충격'으로 봐야 순수 효과가 보인다."""
    d = df.dropna(subset=["corn_anom", "ppt"]).copy()
    # 강수를 구간으로 나눠 각 구간의 평균 수확량 편차(추세대비)를 본다
    d["ppt_bin"] = pd.cut(d.ppt, bins=np.arange(200, 1200, 75))
    g = d.groupby("ppt_bin", observed=True).agg(anom=("corn_anom", "mean"),
                                                n=("corn_anom", "size")).reset_index()
    g = g[g.n >= 50]
    centers = g.ppt_bin.apply(lambda b: b.mid).astype(float)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.axhline(0, color="#9ca3af", lw=1)
    ax.plot(centers, g.anom, "o-", color="#059669")
    ax.set(xlabel="Growing-season precipitation (mm, Mar-Aug)",
           ylabel="Corn yield anomaly vs trend (bu/ac)",
           title="Too little AND too much rain both hurt (hump-shaped response)")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "02_precip_response.png")); plt.close(fig)
    return g, centers


def fig_soil(df: pd.DataFrame):
    """그림3: 토양 보수력(whc) → 수확량. 물이 제한요인인 이유를 보여준다."""
    d = df.dropna(subset=["corn_anom", "whc"]).copy()
    d["whc_bin"] = pd.qcut(d.whc, 8, duplicates="drop")
    g = d.groupby("whc_bin", observed=True).agg(anom=("corn_anom", "mean")).reset_index()
    centers = g.whc_bin.apply(lambda b: b.mid).astype(float)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.axhline(0, color="#9ca3af", lw=1)
    ax.plot(centers, g.anom, "o-", color="#7c3aed")
    ax.set(xlabel="Soil water-holding capacity (whc)",
           ylabel="Corn yield anomaly vs trend (bu/ac)",
           title="Higher water-holding soils buffer yields")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "03_soil_whc.png")); plt.close(fig)


def fig_state_vulnerability(df: pd.DataFrame):
    """그림4: 주별 기상충격 변동성 = 기후 취약도. 최적화의 '어디가 위험한가'와 직결."""
    g = (df.dropna(subset=["corn_anom_pct"])
         .groupby("state_abbr").corn_anom_pct.std().sort_values())
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(g.index, g.values, color="#ea580c")
    ax.set(xlabel="Std of yield anomaly (% of trend)", ylabel="State",
           title="Which states swing most with weather (climate vulnerability)")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "04_state_vulnerability.png")); plt.close(fig)
    return g


def fig_corr(df: pd.DataFrame):
    """그림5: 피처 상관행렬 — 어떤 변수끼리 정보가 겹치는지(다중공선성) 확인."""
    cols = ["corn", "ppt", "whc", "om", "spH", "clay", "slope", "year"]
    c = df[cols].corr()
    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    im = ax.imshow(c, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(cols))); ax.set_xticklabels(cols, rotation=45, ha="right")
    ax.set_yticks(range(len(cols))); ax.set_yticklabels(cols)
    for i in range(len(cols)):
        for j in range(len(cols)):
            ax.text(j, i, f"{c.iloc[i,j]:.2f}", ha="center", va="center", fontsize=8,
                    color="white" if abs(c.iloc[i, j]) > 0.5 else "black")
    fig.colorbar(im, fraction=0.046)
    ax.set_title("Feature correlations")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "05_correlations.png")); plt.close(fig)
    return c


def run():
    df = build_panel("corn")
    print("=" * 70)
    print("EDA — 옥수수 (Corn Belt 12개 주, 1981-2015)")
    print("=" * 70)
    print(f"관측치: {len(df):,} 카운티-연도  |  카운티 수: {df.stco.nunique():,}  "
          f"|  주: {df.state.nunique()}")
    print(f"온도(GDD) 피처: {'있음' if 'gdd' in df else '없음 (egress 차단으로 미확보)'}")

    nat = fig_trend_and_shocks(df)
    tech_gain = (nat.trend_mean.iloc[-1] - nat.trend_mean.iloc[0]) / (nat.year.iloc[-1] - nat.year.iloc[0])
    print(f"\n[그림1] 기술추세: 연평균 +{tech_gain:.1f} bu/ac 로 꾸준히 상승.")
    print("        그 위에 1983·1988·1993·2012 년 큰 하강 = 그해 '기상충격'.")
    print(f"        2012 실제평균 {nat.loc[nat.year==2012,'yield_mean'].iloc[0]:.0f} vs "
          f"추세기대 {nat.loc[nat.year==2012,'trend_mean'].iloc[0]:.0f} → 가뭄이 추세를 크게 밑돌게 함.")

    g2, _ = fig_precip_response(df)
    peak = g2.loc[g2.anom.idxmax(), "ppt_bin"].mid
    print(f"\n[그림2] 강수 반응은 언덕형(hump). 대략 {peak:.0f}mm 부근에서 수확량이 최대,")
    print("        그보다 적으면 가뭄, 많으면 침수/일조부족으로 둘 다 감소.")
    print("        → 선형이 아니라 '최적점이 있는' 관계라 트리모델이 적합.")

    fig_soil(df)
    print("\n[그림3] 보수력(whc)이 높은 토양일수록 기상충격을 덜 받음(완충).")

    gv = fig_state_vulnerability(df)
    print(f"\n[그림4] 기상 변동성 최대 주: {gv.index[-1]} ({gv.iloc[-1]:.1f}%), "
          f"최소: {gv.index[0]} ({gv.iloc[0]:.1f}%).")
    print("        → 변동이 큰 주가 기후위험이 크고, 재배치·보험 논의의 1순위.")

    c = fig_corr(df)
    print(f"\n[그림5] year~corn 상관 {c.loc['year','corn']:.2f}(기술추세), "
          f"ppt~corn {c.loc['ppt','corn']:.2f}, whc~corn {c.loc['whc','corn']:.2f}.")
    print("        sand/silt/clay 는 서로 강상관이라 대표값만 사용(다중공선성 관리).")
    print("\n그림 5장 저장 →", FIG)
    return df


if __name__ == "__main__":
    run()
