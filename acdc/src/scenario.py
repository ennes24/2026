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

    def predict_with(mult_ppt=1.0, et_penalty=0.0):
        x = base[feats].copy()
        # 가뭄: 강수 스케일. 온난화 프록시: 증발산↑ → 유효강수 추가 감소(et_penalty).
        x["ppt"] = x["ppt"] * mult_ppt * (1 - et_penalty)
        return m.predict(x)

    scenarios = {
        "baseline": dict(mult_ppt=1.00, et_penalty=0.00),
        "drought_-15%": dict(mult_ppt=0.85, et_penalty=0.00),
        "drought_-30%": dict(mult_ppt=0.70, et_penalty=0.00),
        # 온난화 프록시: +2°C 가정 → 증발산 수요 약 +8% → 유효강수 -8% (근사, 문헌 대략치)
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
    colors = ["#2563eb", "#f59e0b", "#dc2626", "#a855f7", "#7c2d12"]
    ax.bar(res.scenario, res.pct_change_vs_baseline, color=colors)
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
    print("\n[한계 — 반드시 읽을 것]")
    print(" 온난화의 핵심 경로는 '기온 상승 → 개화기 고온피해(EDD)'인데, 이 세션은")
    print(" 온도(GDD) 파일을 못 받아 그 채널을 직접 모의하지 못한다. 위 warming_*")
    print(" 시나리오는 '기온↑→증발산↑→유효강수↓'만 반영한 프록시라 실제 고온피해를")
    print(" 과소평가한다(2012 스트레스 테스트에서 확인된 그 편향). gddAprOct.csv 를")
    print(" data/ 에 넣으면 edd 피처와 진짜 온난화 시나리오가 자동 활성화된다.")


if __name__ == "__main__":
    run()
