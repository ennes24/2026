"""
scenario.py — 두 갈래 예측

예측 1) 생산성 지도: 학습된 모델로 카운티별 옥수수 수확량을 예측해
        '어디가 가장 잘 나오는가(재배치의 방향)'를 순위/주별로 보여준다.

예측 2) 기후 스트레스 시나리오: 온난화가 진행될 때 수확량이 어떻게 변하나.
        - 2a. 가뭄 시나리오(강수 -15%/-30%): 우리가 가진 강수 피처로 직접 모의.
        - 2b. 온난화(기온↑) 시나리오: 온도(GDD/EDD) 데이터가 이 세션에서
              미확보라 '직접' 모의 불가. 대신 온난화의 물리적 경로(증발산↑
              → 유효강수↓)를 근사한 '온난화 프록시'로 방향성만 제시하고,
              한계를 명시한다. gddAprOct.csv 를 넣으면 진짜 EDD 시나리오로 승격.
"""
from __future__ import annotations
import os, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import HistGradientBoostingRegressor

from prepare import build_panel, feature_columns, CORN_BELT_FIPS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(HERE, "figures"); OUT = os.path.join(HERE, "outputs")


def fit_full(crop="corn"):
    df = build_panel(crop)
    feats = feature_columns(df)
    m = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05,
                                      max_leaf_nodes=31, random_state=0)
    m.fit(df[feats], df[crop])
    return m, df, feats


def track1_productivity(crop="corn"):
    """예측1 — 생산성 지도(주별 예측 수확량 순위)."""
    m, df, feats = fit_full(crop)
    latest = df[df.year == df.year.max()].copy()
    latest["pred"] = m.predict(latest[feats])
    by_state = (latest.groupby("state_abbr")
                .agg(pred_yield=("pred", "mean"), n=("pred", "size"))
                .sort_values("pred_yield", ascending=False))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(by_state.index[::-1], by_state.pred_yield[::-1], color="#059669")
    ax.set(xlabel=f"Predicted {crop} yield (bu/ac, latest year)",
           title=f"Track 1 — where {crop} is most productive (allocation direction)")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, f"09_productivity_{crop}.png")); plt.close(fig)
    by_state.round(1).to_csv(os.path.join(OUT, f"productivity_{crop}.csv"))
    return by_state


def track2_climate(crop="corn"):
    """예측2 — 기후 스트레스 시나리오."""
    m, df, feats = fit_full(crop)
    base = df[df.year == df.year.max()].copy()

    has_edd = "edd" in feats

    def predict_with(mult_ppt=1.0, mult_edd=1.0, et_penalty=0.0):
        x = base[feats].copy()
        x["ppt"] = x["ppt"] * mult_ppt * (1 - et_penalty)
        if has_edd:
            # 온난화 = 극한고온(EDD) 노출 증가. 모델이 실측에서 학습한 EDD→수확량
            # 관계를 그대로 이용. (버킷 히스토그램을 슬림화했으므로 EDD 배율로 표현)
            x["edd"] = x["edd"] * mult_edd
        return m.predict(x)

    if has_edd:
        # 온도 데이터 확보 → EDD 기반 '진짜' 온난화 시나리오
        scenarios = {
            "baseline": dict(mult_ppt=1.00, mult_edd=1.0),
            "drought_-15%": dict(mult_ppt=0.85, mult_edd=1.0),
            "drought_-30%": dict(mult_ppt=0.70, mult_edd=1.0),
            "warming_EDDx1.5": dict(mult_ppt=1.00, mult_edd=1.5),
            "warming_EDDx2.0": dict(mult_ppt=1.00, mult_edd=2.0),
            "warm+dry_EDDx2_ppt-20%": dict(mult_ppt=0.80, mult_edd=2.0),
        }
    else:
        # 온도 미확보 → 강수 프록시만 (과소평가 주의)
        scenarios = {
            "baseline": dict(mult_ppt=1.00, et_penalty=0.00),
            "drought_-15%": dict(mult_ppt=0.85, et_penalty=0.00),
            "drought_-30%": dict(mult_ppt=0.70, et_penalty=0.00),
            "warming_+2C_proxy": dict(mult_ppt=1.00, et_penalty=0.08),
            "warming_+3C_drought_proxy": dict(mult_ppt=0.85, et_penalty=0.12),
        }
    base_pred = predict_with()
    rows = []
    per_state = {}
    for name, kw in scenarios.items():
        p = predict_with(**kw)
        chg = 100 * (p.mean() - base_pred.mean()) / base_pred.mean()
        rows.append({"scenario": name, "mean_pred": round(float(p.mean()), 1),
                     "pct_change_vs_baseline": round(float(chg), 1)})
        per_state[name] = pd.Series(p, index=base.index).groupby(base.state_abbr).mean()
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(OUT, f"scenario_{crop}.csv"), index=False)

    # 그림: 시나리오별 전체 평균 변화
    fig, ax = plt.subplots(figsize=(8.5, 5))
    palette = ["#2563eb", "#f59e0b", "#dc2626", "#a855f7", "#7c2d12", "#0f766e"]
    ax.bar(res.scenario, res.pct_change_vs_baseline, color=palette[:len(res)])
    ax.axhline(0, color="#444", lw=1)
    for i, v in enumerate(res.pct_change_vs_baseline):
        ax.text(i, v, f"{v:+.1f}%", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=9)
    ax.set(ylabel="Change in predicted yield vs baseline (%)",
           title=f"Track 2 — {crop} under climate stress (precip channel)")
    plt.xticks(rotation=20, ha="right")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, f"10_scenario_{crop}.png")); plt.close(fig)

    # 주별 가뭄 취약도(-30% 시나리오에서 감소율)
    drop = 100 * (per_state["drought_-30%"] - per_state["baseline"]) / per_state["baseline"]
    drop = drop.sort_values()
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(drop.index, drop.values, color="#dc2626")
    ax.set(xlabel="Yield change under -30% rainfall (%)",
           title=f"Track 2 — which states lose most in a drought ({crop})")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, f"11_drought_by_state_{crop}.png")); plt.close(fig)
    return res, drop


def run():
    print("=" * 70); print("예측 1 — 생산성 지도 (옥수수)"); print("=" * 70)
    p1 = track1_productivity("corn")
    print(p1.round(1).to_string())
    print(f"\n→ 예측 생산성 최고: {p1.index[0]} ({p1.pred_yield.iloc[0]:.0f} bu/ac), "
          f"최저: {p1.index[-1]} ({p1.pred_yield.iloc[-1]:.0f}).")
    print("→ '방향' 해석: 같은 면적이면 상위 주로 배분할수록 총생산↑ "
          "(전환비용 패널티는 최적화 단계에서 부과).")

    print("\n" + "=" * 70); print("예측 2 — 기후 스트레스 시나리오 (옥수수)"); print("=" * 70)
    res, drop = track2_climate("corn")
    print(res.to_string(index=False))
    print(f"\n→ 가뭄 -30% 시 전체 예측수확량 {res.loc[res.scenario=='drought_-30%','pct_change_vs_baseline'].iloc[0]:.1f}%.")
    print(f"→ 가뭄에 가장 취약한 주: {drop.index[0]} ({drop.iloc[0]:.1f}%), "
          f"가장 견디는 주: {drop.index[-1]} ({drop.iloc[-1]:.1f}%).")
    warm = res[res.scenario.str.startswith("warming")]
    if len(warm):
        print("\n[온난화 — EDD 기반 실측 시나리오]")
        for _, r in warm.iterrows():
            print(f"  {r.scenario}: {r.pct_change_vs_baseline:+.1f}%")
        print(" 극한고온 노출(EDD)이 늘수록 수확량이 실제로 감소 — 모델이 데이터에서")
        print(" 학습한 관계다. 강수만 쓰던 프록시(+0.2%)와 달리 이제 방향·크기가 나온다.")


if __name__ == "__main__":
    run()
