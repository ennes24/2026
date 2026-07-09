"""
climate_model.py — Phase 3 (v3): 기후 예측 모델 A (온난화 시나리오 생성기)

목표: 연도·지역 추세로 미래 온도노출(edd/gdd)·강수(ppt)를 예측 → 온난화 시나리오 입력.
그런데 이 데이터가 실제로 뭐라고 말하는지부터 정직하게 본다.

★ 핵심 발견: 1981–2015 옥수수 벨트에서 **극한고온(EDD)은 증가하지 않았다**
   (추세 −0.046/yr, 사실상 평탄~하락). 강수는 +2.7mm/yr로 증가.
   이는 문헌의 'US Corn Belt warming hole'(여름철 온난화 정체)과 일치한다.

⇒ 함의: 이 지역 관측추세를 그대로 외삽하면 '온난화 시나리오'가 안 나온다.
   따라서 온난화는 **외생(IPCC/기후과학) 가정**으로 부과해야 하며, 단일 예측이 아니라
   시나리오로 다뤄야 한다(가설 H4). Model A 는 (1) 관측추세를 정직히 보고,
   (2) 외생 온난화 델타로 시나리오를 만든다.
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import HistGradientBoostingRegressor

from prepare import build_panel, feature_columns

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(HERE, "figures"); OUT = os.path.join(HERE, "outputs")


def trends(df):
    yr = df.groupby("year").agg(edd=("edd", "mean"), gdd=("gdd", "mean"),
                                ppt=("ppt", "mean"))
    out = {}
    for c in ("edd", "gdd", "ppt"):
        b1, b0 = np.polyfit(yr.index.values, yr[c].values, 1)
        out[c] = (b0, b1, yr[c])
    return out


def run():
    df = build_panel("corn")
    if "edd" not in df.columns:
        raise SystemExit("온도 필요")
    tr = trends(df)
    print("=" * 70); print("Phase 3 — 기후 예측 모델 A (관측추세 진단)"); print("=" * 70)
    for c in ("edd", "gdd", "ppt"):
        b0, b1, series = tr[c]
        print(f"{c}: 추세 {b1:+.3f}/yr  ({series.iloc[0]:.0f}→{series.iloc[-1]:.0f}, "
              f"2050 외삽 {b0+b1*2050:.0f})")
    print("\n★ EDD(극한고온)는 증가 안 함 → 'Corn Belt warming hole'. 관측 외삽으론 온난화 시나리오 불가.")
    print("  ⇒ 온난화는 외생(IPCC) 가정으로 부과하고 '시나리오'로 다룬다 (H4).")

    # 그림22: EDD 관측 + 추세 외삽 + 외생 온난화 시나리오 밴드
    b0, b1, edd_s = tr["edd"]
    hist_yr = edd_s.index.values
    fut = np.arange(2016, 2051)
    proj = b0 + b1 * fut
    edd_2015 = edd_s.iloc[-1]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(hist_yr, edd_s.values, "o-", color="#111", ms=3, label="Observed EDD (1981-2015)")
    ax.plot(fut, proj, "--", color="#6b7280", label="Data-trend extrapolation (warming hole)")
    ax.plot(fut, np.full_like(fut, edd_2015 * 1.3, dtype=float), ":", color="#f59e0b",
            label="Exogenous +mild (IPCC assumption, EDDx1.3)")
    ax.plot(fut, np.full_like(fut, edd_2015 * 1.8, dtype=float), ":", color="#dc2626",
            label="Exogenous +severe (EDDx1.8)")
    ax.set(xlabel="Year", ylabel="Mean EDD (>30C degree-days)",
           title="Model A: data trend shows NO extreme-heat rise; warming must be imposed exogenously")
    ax.legend(fontsize=8.5); fig.tight_layout()
    fig.savefig(os.path.join(FIG, "22_climate_model.png")); plt.close(fig)

    # 시나리오별 옥수수 수확량 (외생 델타를 yield 모델에 투입)
    feats = feature_columns(df)
    m = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05,
                                      max_leaf_nodes=31, random_state=0).fit(df[feats], df["corn"])
    base = df[df.year == df.year.max()].copy()
    def yld(edd_mult=1.0, ppt_mult=1.0):
        x = base[feats].copy(); x["edd"] *= edd_mult; x["ppt"] *= ppt_mult
        return m.predict(x).mean()
    b = yld()
    scen = {
        "data_trend_2050 (관측외삽)": (1.0, 1.0 + (tr['ppt'][1] * 35) / base.ppt.mean()),
        "IPCC_mild (EDDx1.3)": (1.3, 1.0),
        "IPCC_severe (EDDx1.8)": (1.8, 0.95),
    }
    rows = []
    for name, (em, pm) in scen.items():
        y = yld(em, pm); rows.append({"scenario": name, "corn_yield": round(y, 1),
                                      "vs_base_%": round(100 * (y - b) / b, 1)})
    res = pd.DataFrame(rows); res.to_csv(os.path.join(OUT, "climate_scenarios.csv"), index=False)
    print("\n[시나리오별 옥수수 수확량]")
    print(f"  baseline(2015): {b:.1f} bu/ac")
    for _, r in res.iterrows():
        print(f"  {r.scenario:<28}: {r.corn_yield:>6.1f}  ({r['vs_base_%']:+.1f}%)")
    print("\n→ 관측외삽(2050)은 거의 유지(-1.7%, EDD 정체+강수↑). 온난화 피해는 외생 IPCC 가정에서만 나타남.")
    print("→ 이게 v3의 'EDD×2 임의이동'을 대체: 관측은 온난화를 안 보이므로 시나리오는 명시적 가정으로.")
    print("→ 그림22 저장, 수치 → outputs/climate_scenarios.csv")
    return res


if __name__ == "__main__":
    run()
